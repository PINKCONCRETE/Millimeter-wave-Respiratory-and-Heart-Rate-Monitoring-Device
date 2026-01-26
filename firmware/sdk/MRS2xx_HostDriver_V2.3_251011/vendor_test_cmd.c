#include <zephyr/device.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/drivers/wkio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/printk.h>

#include <stdlib.h>
#include <stdbool.h>
#include "string.h"

#include "psic_ll_gpio.h"
#include "psic_gpio_lib.h"
#include "vendor_porting_layer.h"
#include "present_det_env_study.h"

#define VENDOR_TEST_SENSOR_DRIVER_ENA					(1)
#define VENDOR_TEST_FIRMWARE_DOWNLOAD_ENA			(1)

//static const struct device *vendor_i2c = DEVICE_DT_GET(DT_NODELABEL(i2c0));
//static const struct device *vendor_uart = DEVICE_DT_GET(DT_NODELABEL(uart1));
static const struct device *const vendor_gpio = DEVICE_DT_GET(DT_NODELABEL(gpioa));
//static const struct device *flash_device = DEVICE_DT_GET_OR_NULL(DT_CHOSEN(zephyr_flash_controller));

extern int app_get_target_range_callback(sensor_range_t *sensor_range, void *user_data);
extern int app_sensor_err_callback(void *user_data);
extern int vendor_dout_isr_cb_reg(DOUT_ISR_CB_T dout_cb);
extern void dout_isr_callback(void);
extern int app_get_range_spec_callback(uint8_t path, uint16_t *data, uint16_t count);
extern void vendor_disable_lpio(void);
extern void vendor_enable_lpio(void);


#if (VENDOR_TEST_SENSOR_DRIVER_ENA)
#include "sensor_driver.h"
static int cmd_sensor_init(const struct shell *shell, size_t argc, char *argv[])
{
	int ret;
	if (argc > 1) {
		if (strcmp(argv[1], "uart") == 0) {
			sensor_intf_register(&vendor_driver_init, &vendor_uart_write, &vendor_uart_read, &vendor_read_dout_pin_level);
		} else if (strcmp(argv[1], "i2c") == 0) {
			sensor_intf_register(&vendor_driver_init, &vendor_i2c_write, &vendor_i2c_read, &vendor_read_dout_pin_level);
		} else {
			return -1;
		}
	}
	ret = sensor_init();
	if (ret < 0) {
		return -1;
	}
	return 0;
}

static int cmd_sensor_start(const struct shell *shell, size_t argc, char *argv[])
{
	return sensor_start_motion_det();
}

static int cmd_sensor_stop(const struct shell *shell, size_t argc, char *argv[])
{
	return sensor_stop_motion_det();
}

static int cmd_sensor_suspend(const struct shell *shell, size_t argc, char *argv[])
{
	return sensor_suspend(2);
}

static int cmd_sensor_wakeup(const struct shell *shell, size_t argc, char *argv[])
{
	return sensor_wakeup();
}

static int cmd_sensor_onoff(const struct shell *shell, size_t argc, char *argv[])
{
	if (argc > 1) {
		bool on = !!strtoul(argv[1], NULL, 16);
		return sensor_start(on);
	}
	shell_error(shell, "argc param error %d", argc);
	return -1;
}

static int cmd_mwc_cfg_dump(const struct shell *shell, size_t argc, char *argv[])
{
	sensor_info_t info[SECTION_NUM];
	sensor_cfg_get(&info[0]);

	for (int i = 0; i < SECTION_NUM; i++) {
		shell_print(shell, "section %d:", i);
//		shell_print(shell, "sensor radar micro detect %d range 0 - %dmm", info[i].is_micro, info[i].range_mm);
//		shell_print(shell, "sensor radar detect period_ms %dms hold time %dms", info[i].period_ms, info[i].output_time_ms);
		shell_print(shell, "\n");
	}
	return 0;
}

static int cmd_sensor_public_cfg(const struct shell *shell, size_t argc, char *argv[])
{
	int ret = 0;
	uint8_t public_upload_sel;
	uint8_t dout_mode;
	uint8_t dout_report_sel;
	if (argc <= 3) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}
	public_upload_sel = strtoul(argv[1], NULL, 10);
	dout_mode = strtoul(argv[2], NULL, 10);
	dout_report_sel = strtoul(argv[3], NULL, 10);
	shell_print(shell, "public_upload_sel %d dout_mode %d dout_report_sel %d\n",
			public_upload_sel, dout_mode, dout_report_sel);

	sensor_public_cfg(public_upload_sel, dout_mode, dout_report_sel);

exit:
	cmd_mwc_cfg_dump(shell, argc, argv);
	return ret;
}

static int cmd_set_iic_slave_addr(const struct shell *shell, size_t argc, char *argv[])
{
	int ret = 0;
	uint8_t addr = 0x30;

	if (argc <= 1) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}

	addr = strtoul(argv[1], NULL, 16);
	ret = sensor_set_iic_slave_addr(addr);
exit:
	shell_print(shell, "addr 0x%02x\n", addr);
	return ret;
}


static int cmd_get_sync_tick(const struct shell *shell, size_t argc, char *argv[])
{
	shell_print(shell, "tick 0x%02x\n", sensor_get_sync_tick());
	return 0;
}

static int cmd_get_dout_report_sta(const struct shell *shell, size_t argc, char *argv[])
{
	shell_print(shell, "sta 0x%02x\n", sensor_get_dout_report_sta());
	return 0;
}


static int cmd_get_target_range(const struct shell *shell, size_t argc, char *argv[])
{
	sensor_range_t *sensor_range = sensor_get_range_obj();

	if (sensor_range->target_num) {
		for (int i = 0; i < sensor_range->target_num; i++) {
			shell_print(shell, "target[%d] range %d mm\n", i, (uint32_t)sensor_range->target_buf[i]);
		}
	} else {
		shell_print(shell, "no target\n");
	}

	return 0;
}

static int cmd_sensor_info_get(const struct shell *shell, size_t argc, char *argv[])
{
	uint8_t type = 0;
	int ret = 0;

	type = strtoul(argv[1], NULL, 10);

	if (type == 1) {
		ret = sensor_wakeup_read_and_suspend();

	} else if (type == 2) {
		ret = sensor_get_rs_micro_info();

	} else if (type == 3) {
		ret = sensor_get_rs_presence_info();

	} else if (type == 4) {
		ret = sensor_wakeup_read_and_suspend();
		if (ret) {
			return ret;
		}
#if (CONFIG_HOST_IIC_EN == 0)
		hif_delay_us(50000);
#endif
		ret = sensor_get_rs_micro_info();
		if (ret) {
			return ret;
		}
#if (CONFIG_HOST_IIC_EN == 0)
		hif_delay_us(50000);
#endif
		ret = sensor_get_rs_presence_info();
		if (ret) {
			return ret;
		}
#if (CONFIG_HOST_IIC_EN == 0)
		hif_delay_us(50000);
#endif
	} else {
		extern int sensor_report_process(void);
		ret = sensor_report_process();
	}
	return ret;
}


static int cmd_sensor_startup(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;
	ret = sensor_startup();
	if (ret < 0) {
		shell_print(shell, "sensor radar start fail ret %d\n", ret);
		goto exit;
	}
exit:
	return ret;
}

static int cmd_sensor_pram_cfg_startup(const struct shell *shell,
               size_t argc, char **argv)
{
	vendor_disable_lpio();
	int ret = 0;
	ret = sensor_pram_cfg_startup();
	if (ret < 0) {
		shell_print(shell, "sensors pram cfg startup fail ret %d\n", ret);
		goto exit;
	}
exit:
	vendor_enable_lpio();
	return ret;
}


static int cmd_sensor_range_cfg(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;
	uint8_t section_id = 0;
	uint16_t raneg_mm = 0;
	if (argc <= 2) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}
	section_id = strtoul(argv[1], NULL, 10);
	raneg_mm = strtoul(argv[2], NULL, 10);
	shell_print(shell, "section_id[%d] raneg_mm[%d]\n", section_id, raneg_mm);
	ret = sensor_range_cfg(section_id, raneg_mm);
	if (ret < 0) {
		shell_print(shell, "sensor radar start fail ret %d\n", ret);
		goto exit;
	}
exit:
	return ret;
}

static int cmd_sensor_detection_mode_cfg(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;
	if (argc <= 4) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}
	uint8_t section_id = 0;
	uint8_t det_mode = 0;
	uint16_t thr1 = 0;
	uint16_t thr2 = 0;
	shell_print(shell, "section_id[%d] det_mode[%d] thr1[%d] thr2[%d]\n", section_id, det_mode, thr1, thr2);
	ret = sensor_detection_mode_cfg(section_id, det_mode, thr1, thr2);
	if (ret < 0) {
		shell_print(shell, "sensor radar start fail ret %d\n", ret);
		goto exit;
	}
exit:
	return ret;
}

static int cmd_sensor_period_cfg(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;
	uint8_t section_id = 0;
	uint16_t period_ms = 0;
	if (argc <= 2) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}
	section_id = strtoul(argv[1], NULL, 10);
	period_ms = strtoul(argv[2], NULL, 10);
	shell_print(shell, "section_id[%d] period_ms[%d]\n", section_id, period_ms);
	ret = sensor_period_cfg(section_id, period_ms);
	if (ret < 0) {
		shell_print(shell, "sensor radar start fail ret %d\n", ret);
		goto exit;
	}
exit:
	return ret;
}

static int cmd_sensor_app_timeout(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;

	if (argc <= 1) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}

	uint32_t time_s = strtoul(argv[1], NULL, 10);
	vendor_timer_stop();
	/* set 0 stop timer */
	if (time_s > 0) {
		vendor_timer_start(time_s);
	}

exit:
	return ret;
}

static int cmd_sensor_app_lpio_ctrl(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;

	if (argc <= 1) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}

	uint32_t lpio_en = strtoul(argv[1], NULL, 10);
	/* set 0 stop timer */
	if (lpio_en > 0) {
		vendor_enable_lpio();
	} else {
		vendor_disable_lpio();
	}

exit:
	return ret;
}


static int cmd_sensor_app_reg(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = 0;

	if (argc <= 1) {
		shell_error(shell, "argc param error %d", argc);
		ret = -1;
		goto exit;
	}
	bool reg_sync = strtoul(argv[1], NULL, 10);
	sensor_range_info_report_register(&app_get_target_range_callback, NULL);
	sensor_rs_report_register(&app_get_range_spec_callback);
	if (reg_sync) {
		sensor_sync_tick_report_register(&app_sensor_err_callback, NULL);
	} else {
		vendor_dout_isr_cb_reg(&dout_isr_callback);
	}
exit:
	return ret;
}

static int cmd_sensor_app_unreg(const struct shell *shell,
               size_t argc, char **argv)
{
	sensor_range_info_report_register(NULL, NULL);
	sensor_sync_tick_report_register(NULL, NULL);
	sensor_rs_report_register(NULL);
	vendor_dout_isr_cb_reg(NULL);
	return 0;
}

static int cmd_sensor_image_read_fw_ver(const struct shell *shell,
               size_t argc, char **argv)
{
    int ret = 0;
    tlv_info_t tlv_info;

    ret = sensor_image_read_fw_ver(&tlv_info);
    shell_print(shell, "fw_ver[0x%08x] cli_ver[0x%08x]\n", tlv_info.fw_ver, tlv_info.cli_ver);

    return ret;
}


#if (SENSOR_MODEL_MRS261L || SENSOR_MODEL_MRS262) && (SENSOR_ENV_STUDY_ENABLE)
static int cmd_set_env_study(const struct shell *shell,
               size_t argc, char **argv)
{
    int ret = 0;

    if (argc <= 9) {
        shell_error(shell, "argc param error %d", argc);
        ret = -1;
        goto exit;
    }

    uint8_t  mode        = strtoul(argv[1], NULL, 10);
    uint8_t  micr_ndist  = strtoul(argv[2], NULL, 10);
    uint8_t  pres_ndist  = strtoul(argv[3], NULL, 10);
    int16_t  micr_up_thr = strtoul(argv[4], NULL, 10);
    int16_t  pres_up_thr = strtoul(argv[5], NULL, 10);
    uint8_t  micr_cnt    = strtoul(argv[6], NULL, 10);
    uint8_t  pres_cnt    = strtoul(argv[7], NULL, 10);
    uint8_t  micr_len    = strtoul(argv[8], NULL, 10);
    uint8_t  pres_len    = strtoul(argv[9], NULL, 10);

    static int16_t cmd_env_study_peak[2][SENSOR_ENV_STUDY_MAX_BIN] = {0};
    static uint8_t cmd_env_study_thre[SENSOR_ENV_STUDY_MAX_BIN]    = {0};

    static sensor_env_study_ctx_t cmd_micr_ctx;
    cmd_micr_ctx = sensor_env_study_ctx_init(micr_ndist,
                                             micr_up_thr,
                                             micr_cnt,
                                             cmd_env_study_peak[0],
                                             micr_len);

    static sensor_env_study_ctx_t cmd_pres_ctx;
    cmd_pres_ctx = sensor_env_study_ctx_init(pres_ndist,
                                             pres_up_thr,
                                             pres_cnt,
                                             cmd_env_study_peak[1],
                                             pres_len);

    static sensor_env_study_t cmd_ses;
    cmd_ses = SENSOR_ENV_STUDY_INIT_FUNC(mode,
                                         cmd_env_study_thre,
                                         &cmd_micr_ctx,
                                         &cmd_pres_ctx);

    ret = sensor_env_study(&cmd_ses);
    if (ret) {
        shell_error(shell, "[ERR] det env study %d", ret);
        ret = -1;
    }

exit:
    return ret;
}
#endif

#if SENSOR_MODEL_MRS251 || SENSOR_MODEL_RS2111
static int cmd_sensor_set_251_work_mode_info(const struct shell *shell,
               size_t argc, char **argv)
{
    int ret = 0;
    if (argc <= 1) {
        shell_error(shell, "argc param error %d", argc);
        ret = -1;
        goto exit;
    }
    bool high_preformance_mode = strtoul(argv[1], NULL, 10);

    shell_print(shell, "high_preformance_mode[%d]\n", high_preformance_mode);

    ret = sensor_251_work_mode_cfg(high_preformance_mode);
    if (ret < 0) {
        shell_print(shell, "sensor work mode fail ret %d\n", ret);
        goto exit;
    }
exit:
    return ret;
}

static int cmd_sensor_set_251_micro_info(const struct shell *shell,
               size_t argc, char **argv)
{
    int ret = 0;
    if (argc <= 2) {
        shell_error(shell, "argc param error %d", argc);
        ret = -1;
        goto exit;
    }
    uint16_t sensitivity = strtoul(argv[1], NULL, 10);
    uint8_t filter = strtoul(argv[2], NULL, 10);

    shell_print(shell, "sensitivity[%d] filter[%d]\n", sensitivity, filter);

    ret = sensor_251_micro_cfg(sensitivity, filter);
    if (ret < 0) {
        shell_print(shell, "sensor micro fail ret %d\n", ret);
        goto exit;
    }
exit:
    return ret;
}

static int cmd_sensor_set_251_det_info(const struct shell *shell,
               size_t argc, char **argv)
{
    int ret = 0;
    if (argc <= 3) {
        shell_error(shell, "argc param error %d", argc);
        ret = -1;
        goto exit;
    }
    uint16_t respond_delay_ms = strtoul(argv[1], NULL, 10);
    uint16_t det_range = strtoul(argv[2], NULL, 10);
    uint8_t power_back_off = strtoul(argv[3], NULL, 10);

    shell_print(shell, "respond_delay_ms[%d] det_range[%d] power_back_off[%d]\n", respond_delay_ms, det_range, power_back_off);

    ret = sensor_251_det_pram_cfg(respond_delay_ms, det_range, power_back_off);
    if (ret < 0) {
        shell_print(shell, "sensor det fail ret %d\n", ret);
        goto exit;
    }
exit:
    return ret;
}
#endif

SHELL_STATIC_SUBCMD_SET_CREATE(sensor_cmds,
	/* sensor ctrl */
	SHELL_CMD(init, NULL, "[null]", cmd_sensor_init),
	SHELL_CMD(start, NULL, "[null]", cmd_sensor_start),
	SHELL_CMD(startup, NULL, "[null]", cmd_sensor_startup),
	SHELL_CMD(stop, NULL, "[null]", cmd_sensor_stop),
	SHELL_CMD(suspend, NULL, "[on:1/off:0]", cmd_sensor_suspend),
	SHELL_CMD(resume, NULL, "[on:1/off:0]", cmd_sensor_wakeup),
	SHELL_CMD(onoff, NULL, "[on:1/off:0]", cmd_sensor_onoff),
	/* sensor get pram */
	SHELL_CMD(get_sync_tick, NULL, "[null]", cmd_get_sync_tick),
	SHELL_CMD(get_report_sta, NULL, "[null]", cmd_get_dout_report_sta),
	SHELL_CMD(get_trg_pram, NULL, "[null]", cmd_get_target_range),
	SHELL_CMD(get_sensor_info, NULL, "[trg:1/micro:2/pres:3/all:4/proc:else]", cmd_sensor_info_get),
	SHELL_CMD(get_ver, NULL, "[null]", cmd_sensor_image_read_fw_ver),
	/* sensor set pram */
#if SENSOR_MODEL_MRS251 || SENSOR_MODEL_RS2111
	SHELL_CMD(set_251_work_mode_pram, NULL, "[high_preformance_mode]", cmd_sensor_set_251_work_mode_info),
	SHELL_CMD(set_251_micro_pram, NULL, "[sensitivity][filter]", cmd_sensor_set_251_micro_info),
	SHELL_CMD(set_251_det_pram, NULL, "[rsp_delay_ms][range][power_back_off]", cmd_sensor_set_251_det_info),
#endif
	SHELL_CMD(set_pub_pram, NULL, "[public_upload_sel][dout_mode][dout_report_sel]", cmd_sensor_public_cfg),
	SHELL_CMD(set_iic_addr, NULL, "[addr]", cmd_set_iic_slave_addr),
	SHELL_CMD(set_startup, NULL, "[null]", cmd_sensor_pram_cfg_startup),
	SHELL_CMD(set_range, NULL, "[section_id][range_mm]", cmd_sensor_range_cfg),
	SHELL_CMD(set_detection_mode, NULL, "[section_id][det_mode][pram1][pram2]", cmd_sensor_detection_mode_cfg),
	SHELL_CMD(set_period, NULL, "[section_id][period_ms]", cmd_sensor_period_cfg),
#if (SENSOR_MODEL_MRS261L || SENSOR_MODEL_MRS262) && (SENSOR_ENV_STUDY_ENABLE)
	SHELL_CMD(set_env_study, NULL, "[micr:1/pres:2/both:3]"
			"[micr+pres_ndist]"
			"[2*up_thr][2*cnt][2*len]", cmd_set_env_study),
#endif
	SHELL_CMD(app_set_timeout, NULL, "[timeout_s]", cmd_sensor_app_timeout),
	SHELL_CMD(app_set_lpio, NULL, "[lpio_en]", cmd_sensor_app_lpio_ctrl),
	/* sensor app reg */
	SHELL_CMD(app_reg, NULL, "[section_id][period_ms]", cmd_sensor_app_reg),
	SHELL_CMD(app_unreg, NULL, "[section_id][period_ms]", cmd_sensor_app_unreg),
	SHELL_SUBCMD_SET_END
);

static int cmd_sensor_radar(const struct shell *sh, size_t argc, char **argv)
{
	if (argc == 1) {
		shell_help(sh);
		return SHELL_CMD_HELP_PRINTED;
	}

	shell_error(sh, "%s unknown parameter: %s", argv[0], argv[1]);

	return -EINVAL;
}

SHELL_CMD_REGISTER(sensor, &sensor_cmds, "sensor_cmds commands", cmd_sensor_radar);
#endif

#if (VENDOR_TEST_FIRMWARE_DOWNLOAD_ENA)
#include "firmware_download.h"
int burn_delay_ms(uint32_t ms)
{
	k_busy_wait(ms * 1000);
	return 0;
}

static int cmd_sync(const struct shell *shell,
               size_t argc, char **argv)
{
	int ret = fw_download_sync(CONFIG_FW_DOWNLOAD_SYNC_RETRY);
    return ret;
}

int burn_uart_io_enable(uint32_t tx_pin, uint32_t rx_pin)
{
    const struct gpio_psic_config *dev_cfg = vendor_gpio->config;
    gpio_dev_t *gpio = (gpio_dev_t *)dev_cfg->base;

	/* UART AF */
	LL_GPIO_SetPinFuncMode(gpio, tx_pin, LL_GPIOA_P8_F2_UART1_TX);
	LL_GPIO_SetPinFuncMode(gpio, rx_pin, LL_GPIOA_P9_F2_UART1_RX);

    return 0;
}

static int cmd_register_uart(const struct shell *shell,
               size_t argc, char **argv)
{
    burn_uart_io_enable(8, 9);
	vendor_driver_register(&vendor_driver_init, &vendor_uart_write, &vendor_uart_read, &vendor_read_dout_pin_level);
	vendor_image_read_register(&vendor_image_read);
    gpio_pin_configure(vendor_gpio, 2, GPIO_OUTPUT);
    gpio_pin_set_raw(vendor_gpio, 2, 0);
	return 0;
}

static int cmd_register_i2c(const struct shell *shell,
               size_t argc, char **argv)
{
	vendor_driver_register(&vendor_driver_init, &vendor_i2c_write, &vendor_i2c_read, &vendor_read_dout_pin_level);
	vendor_image_read_register(&vendor_image_read);
	gpio_pin_configure(vendor_gpio, 2, GPIO_OUTPUT);
	gpio_pin_set_raw(vendor_gpio, 2, 0);
	return 0;
}

/*
static int cmd_flush(const struct shell *shell,
               size_t argc, char **argv)
{
    return uart_flush();
}
*/
static int cmd_fwdl_start(const struct shell *shell,
               size_t argc, char **argv)
{
	vendor_disable_lpio();

	int ret = sensor_download();
	if (ret < 0) {
		hif_debug_log("sensor_start_download fail ret %d\n", ret);
		goto exit;
	}
	hif_debug_log("firmware download success\n");

	/* wait for new firmware run done*/
	hif_delay_us(50000);
exit:
	vendor_enable_lpio();
	return ret;
}

int burn_uart_io_disable(uint32_t tx_pin, uint32_t rx_pin)
{
    int ret = 0;

    ret = gpio_pin_configure(vendor_gpio, tx_pin, GPIO_DISCONNECTED);
    if (ret != 0) {
        return -1;
    }

    ret = gpio_pin_configure(vendor_gpio, rx_pin, GPIO_DISCONNECTED);
    if (ret != 0) {
        return -2;
    }

    return 0;
}

static int cmd_fwdl_down(const struct shell *shell,
               size_t argc, char **argv)
{
    burn_delay_ms(1000);
    burn_uart_io_disable(8, 9);
    gpio_pin_set_raw(vendor_gpio, 2, 1);

    return 0;
}

static int cmd_fwdl_chipreset(const struct shell *shell,
               size_t argc, char **argv)
{
	return fw_download_reset(3);
}

SHELL_STATIC_SUBCMD_SET_CREATE(fwdl_cmds,
	SHELL_CMD(ureg, NULL, "[]",  cmd_register_uart),
	SHELL_CMD(ireg, NULL, "[]",  cmd_register_i2c),
	SHELL_CMD(sync, NULL, "[]",  cmd_sync),
	SHELL_CMD(start, NULL, "[]",  cmd_fwdl_start),
	SHELL_CMD(reboot, NULL, "[]", cmd_fwdl_down),
	SHELL_CMD(reset, NULL, "[]",  cmd_fwdl_chipreset),
	/* firmware download sample to download firmware from sram or flash*/
	//SHELL_CMD(demo, NULL, "[is_i2c][flash addr][image size]",  cmd_fwdl_demo),
	SHELL_SUBCMD_SET_END
);

static int cmd_fwdl(const struct shell *sh, size_t argc, char **argv)
{
	if (argc == 1) {
		shell_help(sh);
		return SHELL_CMD_HELP_PRINTED;
	}

	shell_error(sh, "%s unknown parameter: %s", argv[0], argv[1]);

	return -EINVAL;
}

SHELL_CMD_REGISTER(fwdl, &fwdl_cmds, "cmd_ui2c commands", cmd_fwdl);
#endif
