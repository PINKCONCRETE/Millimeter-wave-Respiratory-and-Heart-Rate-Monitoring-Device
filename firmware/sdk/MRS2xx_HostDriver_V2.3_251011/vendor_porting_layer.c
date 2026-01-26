#include <zephyr/device.h>
#include <zephyr/drivers/wkio.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/wkio.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/printk.h>

#include <stdbool.h>
#include "string.h"

#include "psic_ll_gpio.h"
#include "psic_ll_utils.h"
#include <psic_ll_lpio.h>
#include <psic_hal_lpio.h>
#include <zephyr/drivers/wkio.h>

#include "vendor_porting_layer.h"

static const struct device *vendor_i2c = DEVICE_DT_GET(DT_NODELABEL(i2c0));
static const struct device *vendor_uart = DEVICE_DT_GET(DT_NODELABEL(uart1));
static const struct device *const vendor_gpio = DEVICE_DT_GET(DT_NODELABEL(gpioa));
static const struct device *vendor_wakeup_gpio = DEVICE_DT_GET(DT_NODELABEL(wkio0));
static const struct device *flash_device = DEVICE_DT_GET_OR_NULL(DT_CHOSEN(zephyr_flash_controller));
static struct k_timer vendor_timer;

DOUT_ISR_CB_T vendor_dout_cb;
TIMER_ISR_CB_T vendor_timer_cb;

void debug_hexdump(char *str_tag, uint8_t *data, uint32_t len)
{
    const uint8_t *p = data;
    uint8_t line_len;

    if (str_tag) {
        hif_debug_log("%s:\n", str_tag);
    }

    while (len) {
        line_len = HIF_MIN(len, 16);
        for (int i = 0; i < line_len; i++) {
            hif_debug_log("%02x ", *p);
            p++;
        }
        hif_debug_log("\n");
        len -= line_len;
    }
    hif_debug_log("\n");
}

void segment_dump(bool bstart, uint8_t *data, uint8_t size)
{
    static uint8_t line_pos = 0;
    const uint8_t *p = data;

    if (bstart == true) {
        line_pos = 0;
    }

    while (size--) {
        if (!line_pos) {
            hif_debug_log("\n");
        }
        hif_debug_log("%02x ", *p);
        line_pos = (line_pos + 1) & 0xF;
        p++;
    }
    hif_debug_log("\n");
}

void vendor_driver_register(void *init_cb, void *write_cb, void *read_cb, void *dout_read_cb)
{
    fw_download_register((FWDL_INIT_CB_T)init_cb,
                         (FWDL_WR_CB_T)write_cb,
                         (FWDL_RD_CB_T)read_cb);

    sensor_intf_register((HIF_INIT_CB_T)init_cb,
                         (HIF_WR_CB_T)write_cb,
                         (HIF_RD_CB_T)read_cb,
                         (DOUT_LEVEL_RD_T)dout_read_cb);
}

void vendor_image_read_register(void *image_read_cb)
{
    fw_image_read_register((FWDL_IMAGE_READ_CB_T)image_read_cb);
}

int vendor_image_read(uint32_t offset, void *data, uint32_t len)
{
    int ret;
    uint32_t flash_addr =  0x32000 + offset;
    ret = flash_read(flash_device, flash_addr, (uint8_t *)data, len);
    return ret;
}

int vendor_uart_write(uint8_t *pbuff, uint32_t len, uint32_t timeout)
{
    for (int i = 0; i < len; i++) {
        uart_poll_out(vendor_uart, pbuff[i]);
    }
    return 0;
}

int vendor_uart_read(uint8_t *pbuff, uint32_t len, uint32_t timeout)
{
    int ret = 0;
    bool blocked = !timeout;

    for (int i = 0; i < len; i++) {
        do {
            ret = uart_poll_in(vendor_uart, &pbuff[i]);
            if ((!blocked) && (timeout == 0)) {
                if (ret < 0) {
                    return ret;
                }
            }
            timeout--;
        } while (ret);
    }
    return ret;
}

int vendor_i2c_write(uint8_t *pbuff, uint32_t len, uint32_t timeout)
{
    struct i2c_msg msg[1];
    msg[0].buf = (uint8_t *)pbuff;
    msg[0].len = len;
    msg[0].flags = I2C_MSG_WRITE | I2C_MSG_STOP;
    return i2c_transfer(vendor_i2c, msg, 1, 0x30);
}

int vendor_i2c_read(uint8_t *pbuff, uint32_t len, uint32_t timeout)
{
    struct i2c_msg msg[1];
    msg[0].buf = (uint8_t *)pbuff;
    msg[0].len = len;
    msg[0].flags = I2C_MSG_READ | I2C_MSG_STOP;
    return i2c_transfer(vendor_i2c, msg, 1, 0x30);
}

int vendor_driver_init(void)
{
    uint32_t i2c_cfg = I2C_SPEED_SET(I2C_SPEED_FAST) | I2C_MODE_CONTROLLER;

    if (!device_is_ready(vendor_uart)) {
        printk("Device %s is not ready", vendor_uart->name);
        return -1;
    }

    if (!device_is_ready(vendor_i2c)) {
        printk("Device %s is not ready", vendor_i2c->name);
        return -1;
    }
    if (i2c_configure(vendor_i2c, i2c_cfg) < 0) {
        printk("I2C %s config master with fast speed and 7 bit addr failed\n", vendor_i2c->name);
        return -1;
    }
    return 0;
}

uint8_t vendor_read_dout_pin_level(void)
{
    gpio_pin_configure(vendor_gpio, 3, GPIO_INPUT);
    return (uint8_t)gpio_pin_get_raw(vendor_gpio, 3);
}

static void vendor_dout_wakeup_io_isr_cb(uint32_t irq_pins, void *data)
{
    if (irq_pins & BIT(3)) {
        hif_debug_log("host wakeup for dout rising/falling edge\n");
        if (vendor_dout_cb) {
            vendor_dout_cb();
        }
    }
}

int vendor_dout_isr_cb_reg(DOUT_ISR_CB_T dout_cb)
{
    if (device_is_ready(vendor_wakeup_gpio)) {
        wkio_wake_config(vendor_wakeup_gpio, 3, WKIO_MODE_EDGE, WKIO_INT_TRIG_BOTH);
        wkio_callback_add(vendor_wakeup_gpio, vendor_dout_wakeup_io_isr_cb, NULL);
    }
    vendor_dout_cb = dout_cb;
    return 0;
}

void vendor_disable_lpio(void)
{
    ll_lpio_conf_t *lpioCfg = HAL_Lpio_GetObj();
    if (vendor_dout_cb) {
        HAL_Lpio_UnSetLpio(lpioCfg, BIT(3));
        k_busy_wait(3);
    }
}

void vendor_enable_lpio(void)
{
    ll_lpio_conf_t *lpioCfg = HAL_Lpio_GetObj();
    if (vendor_dout_cb) {
        HAL_Lpio_SetLpio(lpioCfg, BIT(3));
        k_busy_wait(3);
    }
}

static void vendor_timer_isr_cb(struct k_timer *timer)
{
    if (vendor_timer_cb) {
        hif_debug_log("timer isr\n");
        vendor_timer_cb();
    }
}

int vendor_timer_isr_cb_reg(TIMER_ISR_CB_T timer_cb)
{
    k_timer_init(&vendor_timer, vendor_timer_isr_cb, NULL);
    vendor_timer_cb = timer_cb;
    return 0;
}

void vendor_timer_start(uint32_t time_s)
{
    k_timer_start(&vendor_timer, K_SECONDS(time_s), K_SECONDS(time_s));
}

void vendor_timer_stop(void)
{
    k_timer_stop(&vendor_timer);
}




