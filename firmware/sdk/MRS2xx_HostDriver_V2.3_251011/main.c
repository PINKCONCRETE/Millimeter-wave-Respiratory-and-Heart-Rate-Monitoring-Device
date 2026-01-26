/**
 *   @file  main.c
 *
 *   @brief
 *      APIs Implementation of Host Interface Message.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2022 Possumic, Inc.
 *
 */

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <stdbool.h>
#include <string.h>

#include "vendor_porting_layer.h"
#include "firmware_download.h"
#include "sensor_driver.h"
#include "present_det_env_study.h"

#define APP_CONFIG_STANDBY_DET_RANGE                            (6000)
#define APP_CONFIG_STANDBY_DET_PERIOD                           (300)
#define APP_CONFIG_EXTERNAL_DET_EN                              (0)
#define APP_CONFIG_EXTERNAL_I0                                  (5)
#define APP_CONFIG_EXTERNAL_LEVEL_SEL                           (0)
#define APP_CONFIG_MICRO_THRESH_SEL                             (18)

#define APP_CONFIG_TIMER_PERIOD                                 (10)

#define APP_ENV_STUDY_MICR_GROUP_DIST                           (3)
#define APP_ENV_STUDY_MICR_UP_THRESHOLD                         (2)
#define APP_ENV_STUDY_MICR_STUDY_CNT                            (10)
#define APP_ENV_STUDY_MICR_SPECTRUM_LEN                         (40)

#define APP_ENV_STUDY_PRES_GROUP_DIST                           (3)
#define APP_ENV_STUDY_PRES_UP_THRESHOLD                         (3)
#define APP_ENV_STUDY_PRES_STUDY_CNT                            (10)
#define APP_ENV_STUDY_PRES_SPECTRUM_LEN                         (40)

static struct k_sem g_dout_sem;

__attribute__((weak)) void vendor_disable_lpio(void)
{

}

__attribute__((weak)) void vendor_enable_lpio(void)
{

}

int app_get_target_range_callback(sensor_range_t *sensor_range, void *user_data)
{
    if (sensor_range->target_num) {
        for (int i = 0; i < sensor_range->target_num; i++) {
            hif_debug_log("target[%d] range %d mm\n",
                          i, (uint32_t)sensor_range->target_buf[i]);
        }
    } else {
        hif_debug_log("no target\n");
    }
    return 0;
}

int app_get_range_spec_callback(uint8_t path, uint16_t *data, uint16_t count)
{
    char *range_spec_str = (path == SENSOR_RANGE_SPEC_MMOTION) ?
                           "mico_spectrum" : "pres_spectrum";

    hif_debug_log("%s[0~%d]: ", range_spec_str, count - 1);

    for (uint16_t i = 0; i < count; i++) {
        hif_debug_log("%d ", data[i]);
    }
    hif_debug_log("\n");

    return 0;
}

int app_sensor_err_callback(void *user_data)
{
    vendor_timer_stop();

#if (CONFIG_FW_DOWNLOAD_SRAM == 0)
    /* compatible fw is already running in flash */
    sensor_stop_motion_det();
#endif

    hif_delay_us(50000);
    int ret = sensor_download();
    if (ret < 0) {
        hif_debug_log("sensor_start_download fail ret %d\n", ret);
        goto exit;
    }
    hif_debug_log("firmware download success\n");

    /* wait for new firmware run done*/
    hif_delay_us(50000);

    ret = sensor_startup();
    if (ret < 0) {
        hif_debug_log("sensor radar start fail ret %d\n", ret);
        goto exit;
    }

#if (CONFIG_HOST_SYNC_EN == 0)
    /* sensor_get_sync_tick() will auto suspend sensor */
    ret = sensor_wakeup();
#endif

exit:
    vendor_timer_start(APP_CONFIG_TIMER_PERIOD);
    return ret;
}

bool sensor_err;
void dout_isr_callback(void)
{
    sensor_err = false;
    vendor_disable_lpio();
#if (CONFIG_HOST_SYNC_EN == 0)
    if (vendor_read_dout_pin_level()) {
        /* wait for dout err time */
        hif_delay_us(12000);
        if (vendor_read_dout_pin_level() == 0) {
            hif_debug_log("sensor err!!\n");
            sensor_err = true;
        }
    }
#endif
    hif_debug_log("dout rising or falling edge isr\n");
    k_sem_give(&g_dout_sem);
}

void timer_isr_callback(void)
{
    static int timer_cnt = 0;
    hif_debug_log("period %d \n", timer_cnt++);

    k_sem_give(&g_dout_sem);
}

void main(void)
{
#if CONFIG_HOST_IIC_EN
    vendor_driver_register(&vendor_driver_init,
                           &vendor_i2c_write,
                           &vendor_i2c_read,
                           &vendor_read_dout_pin_level);
#else
    vendor_driver_register(&vendor_driver_init,
                           &vendor_uart_write,
                           &vendor_uart_read,
                           &vendor_read_dout_pin_level);
#endif

    vendor_image_read_register(&vendor_image_read);

#if (CONFIG_FW_DOWNLOAD_SRAM == 0)
    /* compatible fw is already running in flash */
    sensor_stop_motion_det();
#endif

    int ret = sensor_download();
    if (ret < 0) {
        hif_debug_log("sensor_start_download fail ret %d\n", ret);
        return;
    }
    hif_debug_log("firmware download success\n");

    /* wait for new firmware run done*/
    hif_delay_us(500000);

    ret = sensor_startup();
    if (ret < 0) {
        hif_debug_log("sensor start fail ret %d\n", ret);
        return ;
    }

    /* wait for default pram run done*/
    hif_delay_us(500000);

#if SENSOR_MODEL_MRS251 || SENSOR_MODEL_RS2111
    ret = sensor_251_work_mode_cfg(SENSOR_251_WORK_MODE_CFG);
    if (ret < 0) {
        hif_debug_log("sensor work mode cfg fail ret %d\n", ret);
        return ;
    }

    ret = sensor_251_micro_cfg(SENSOR_251_MICRO_SENSITIVITY_CFG,
                               SENSOR_251_MICRO_FILTER_CFG);
    if (ret < 0) {
        hif_debug_log("sensor micro cfg fail ret %d\n", ret);
        return ;
    }

    ret = sensor_251_det_pram_cfg(SENSOR_251_RESPOND_DELAY_MS_CFG,
                                  SENSOR_251_DET_RANGE_CFG,
                                  SENSOR_251_BACK_OFF_CFG);
    if (ret < 0) {
        hif_debug_log("sensor det pram cfg fail ret %d\n", ret);
        return ;
    }

#else
    ret = sensor_range_cfg(SECTION_STANDBY_ID, APP_CONFIG_STANDBY_DET_RANGE);
    if (ret < 0) {
        hif_debug_log("sensor range cfg fail ret %d\n", ret);
        return ;
    }

#if CONFIG_HOST_EXTERNAL_DET_EN
    ret = sensor_detection_mode_cfg(SECTION_STANDBY_ID,
                                    SENSOR_EXTERNAL_EN,
                                    APP_CONFIG_EXTERNAL_I0,
                                    APP_CONFIG_EXTERNAL_LEVEL_SEL);
#else
    ret = sensor_detection_mode_cfg(SECTION_STANDBY_ID,
                                    SENSOR_MICRO_EN,
                                    APP_CONFIG_MICRO_THRESH_SEL,
                                    APP_CONFIG_MICRO_THRESH_SEL);
#endif

    if (ret < 0) {
        hif_debug_log("sensor thresh cfg fail ret %d\n", ret);
        return ;
    }

    ret = sensor_period_cfg(SECTION_STANDBY_ID, APP_CONFIG_STANDBY_DET_PERIOD);
    if (ret < 0) {
        hif_debug_log("sensors period cfg fail ret %d\n", ret);
        return ;
    }
#endif

    ret = sensor_pram_cfg_startup();
    if (ret < 0) {
        hif_debug_log("sensors pram cfg startup fail ret %d\n", ret);
    } else {
        hif_debug_log("motion sensor configure and start success\n");
    }

    sensor_range_info_report_register(&app_get_target_range_callback, NULL);
    sensor_rs_report_register(&app_get_range_spec_callback);
#if CONFIG_HOST_SYNC_EN
    sensor_sync_tick_report_register(&app_sensor_err_callback, NULL);
#endif
    vendor_dout_isr_cb_reg(&dout_isr_callback);

#if (SENSOR_MODEL_MRS261L || SENSOR_MODEL_MRS262) && (SENSOR_ENV_STUDY_ENABLE)
    int16_t ctx_buf[2][SENSOR_ENV_STUDY_MAX_BIN] = {0};
    uint8_t thr_buf[SENSOR_ENV_STUDY_MAX_BIN]    = {0};

    sensor_env_study_ctx_t micr_ctx;
    micr_ctx = sensor_env_study_ctx_init(APP_ENV_STUDY_MICR_GROUP_DIST,
                                         APP_ENV_STUDY_MICR_UP_THRESHOLD,
                                         APP_ENV_STUDY_MICR_STUDY_CNT,
                                         ctx_buf[0],
                                         APP_ENV_STUDY_MICR_SPECTRUM_LEN);

    sensor_env_study_ctx_t pres_ctx;
    pres_ctx = sensor_env_study_ctx_init(APP_ENV_STUDY_PRES_GROUP_DIST,
                                         APP_ENV_STUDY_PRES_UP_THRESHOLD,
                                         APP_ENV_STUDY_PRES_STUDY_CNT,
                                         ctx_buf[1],
                                         APP_ENV_STUDY_PRES_SPECTRUM_LEN);

    sensor_env_study_t ses = SENSOR_ENV_STUDY_INIT(SENSOR_ENV_STUDY_ALL_MODE,
                                                   thr_buf,
                                                   &micr_ctx,
                                                   &pres_ctx);

    ret = sensor_env_study(&ses);
    if (ret) {
        return;
    }
#endif

    tlv_info_t tlv_info;
    sensor_image_read_fw_ver(&tlv_info);
    hif_debug_log("fw_ver[0x%08x] cli_ver[0x%08x]\n", tlv_info.fw_ver, tlv_info.cli_ver);

    vendor_timer_isr_cb_reg(&timer_isr_callback);
    vendor_timer_start(APP_CONFIG_TIMER_PERIOD);

    k_sem_init(&g_dout_sem, 0, 1);
    do {
        k_sem_take(&g_dout_sem, K_FOREVER);
        if (sensor_err) {
            app_sensor_err_callback(NULL);
        } else {
            sensor_main_loop_run(CONFIG_HOST_SYNC_EN);
        }
        vendor_enable_lpio();
    } while (1);
    return ;
}
