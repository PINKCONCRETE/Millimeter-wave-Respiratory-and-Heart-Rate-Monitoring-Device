/*
 *   @file  vendor_porting_layer.h
 *
 *   @brief
 *      Header file for Host Interface Message Definition.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2022 Possumic, Inc.
 *
 */
#ifndef __VENDOR_PORTING_LAYER_H__
#define __VENDOR_PORTING_LAYER_H__

/* Include Files */

#ifdef __cplusplus
extern "C" {
#endif

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/types.h>
#include <zephyr/sys/printk.h>
#include <stdbool.h>
#include <string.h>

#include "firmware_download.h"
#include "sensor_driver.h"

#define CONFIG_HOST_IIC_EN                  (1)
#define CONFIG_HOST_SYNC_EN                 (1)

#define HIF_MIN(a, b)                      (((a) < (b)) ? (a) : (b))

#define hif_debug_log(...)                   printk(__VA_ARGS__)
//#define hif_debug_log(fmt, ...)            printk("[%05d]"fmt, __LINE__, ##__VA_ARGS__)
#define hif_debug_verb(...)                //printk(__VA_ARGS__)

#define hif_delay_us(n)                    k_busy_wait(n)
#define hif_memcpy(d, s, n)                memcpy(d, s, n)
#define hif_memset(d, v, n)                memset(d, v, n)

#define hif_verb_hexdump(s, d, n)          //debug_hexdump(s, d, n)
#define hif_verb_segmentdump(s, d, n)      //segment_dump(s, d, n)

typedef void (*DOUT_ISR_CB_T)(void);
typedef void (*TIMER_ISR_CB_T)(void);
int vendor_dout_isr_cb_reg(DOUT_ISR_CB_T dout_cb);
uint8_t vendor_read_dout_pin_level(void);
int vendor_image_read(uint32_t offset, void *data, uint32_t len);
int vendor_driver_init(void);
int vendor_uart_write(uint8_t *pbuff, uint32_t len, uint32_t timeout);
int vendor_uart_read(uint8_t *pbuff, uint32_t len, uint32_t timeout);
int vendor_i2c_write(uint8_t *pbuff, uint32_t len, uint32_t timeout);
int vendor_i2c_read(uint8_t *pbuff, uint32_t len, uint32_t timeout);
void vendor_driver_register(void *init_cb, void *write_cb, void *read_cb, void *dout_read_cb);
void vendor_image_read_register(void *image_read_cb);

int vendor_timer_isr_cb_reg(TIMER_ISR_CB_T timer_cb);
void vendor_timer_start(uint32_t time_s);
void vendor_timer_stop(void);

/* debug modules */
void debug_hexdump(char *str_tag, uint8_t *data, uint32_t len);
void segment_dump(bool bstart, uint8_t *data, uint8_t size);
#ifdef __cplusplus
}
#endif
#endif /* __VENDOR_PORTING_LAYER_H__ */
