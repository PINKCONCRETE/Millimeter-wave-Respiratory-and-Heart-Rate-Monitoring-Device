/**
 *   @file  sensor_driver_mrs251_rs2111fd.c
 *
 *   @brief
 *      APIs Implementation of Host Interface Message.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2025 Possumic, Inc.
 *
 */
#include "vendor_porting_layer.h"
#include "sensor_driver.h"

#if SENSOR_MODEL_MRS251 || SENSOR_MODEL_RS2111
#define HIF_SENSOR_PARAM_CFG_CMD                0x60

#define SENSOR_251_LOW_POWER_PERIOD_MIN                     (20)
#define SENSOR_251_HIGH_PREFORMANCE_PERIOD_MIN              (100)
#define SENSOR_251_PERIOD_MAX                               (400)

#define SENSOR_251_LOW_POWER_MICRO_EN_CONSTANT_PARAM        (BIT(0))
#define SENSOR_251_LOW_POWER_MICRO_EN                       (BIT(1))

uint8_t sensor_251_det_range_tab[] = {
     0,  1, 17, 18, 19, 20, 21, 22,
    23, 24, 25, 26, 27, 28, 29, 30,
    31,
};

#define SENSOR_251_LOW_POWER_MICRO_FILTER0_PARAM            (0)
uint8_t sensor_251_low_power_filter1_tab[] = {
     32, 18, 10, 7,
};
uint8_t sensor_251_low_power_filter2_tab[] = {
     7, 7, 7, 7, 0,
};
#define SENSOR_251_HIGH_PREFORMANCE_FILTER0_PARAM           (1)

struct sensor_251_cfg_t {
    /* sensor param cfg */
    uint8_t     power_back_off;
    uint8_t     det_range;
    uint16_t    respond_delay_ms;
    uint16_t    micro_sensitivity;
    uint8_t     micro_filter;
    bool        high_preformance_mode;
    /* output param cfg */
    bool output_en;
	uint16_t output_time_ms;
	uint8_t  output_mode;
	uint8_t  output_io;
	uint8_t  output_have_target_pram;
	uint8_t  output_no_target_pram;
	uint8_t  decetion;
} sensor_251_cfg;

int sensor_param_config(void)
{
    uint8_t buf[64];
    uint8_t *tlv = &buf[0];

    /* must be set frist */
    TLV_ADD_U8(tlv, SENSOR_SECTION_SEL_TLV, 0);
    TLV_ADD_U8(tlv, SENSOR_SECTION_EN_TLV, 1);

    TLV_ADD_U8(tlv, SENSOR_POWER_BACK_OFF_TLV,
                    ((sensor_251_cfg.power_back_off << 3) & 0xf0) |
                      SENSOR_POWER_BACK_CONSTANT_PARAM);

    TLV_ADD_U8(tlv, SENSOR_251_WORK_MODE_TLV, sensor_251_cfg.high_preformance_mode);

    if (sensor_251_cfg.respond_delay_ms > SENSOR_251_PERIOD_MAX) {
        sensor_251_cfg.respond_delay_ms = SENSOR_251_PERIOD_MAX;

    } else if ((sensor_251_cfg.respond_delay_ms < SENSOR_251_LOW_POWER_PERIOD_MIN) && (sensor_251_cfg.high_preformance_mode == false)) {
        sensor_251_cfg.respond_delay_ms = SENSOR_251_LOW_POWER_PERIOD_MIN;

    } else if ((sensor_251_cfg.respond_delay_ms < SENSOR_251_HIGH_PREFORMANCE_PERIOD_MIN) && (sensor_251_cfg.high_preformance_mode == true)) {
        sensor_251_cfg.respond_delay_ms = SENSOR_251_HIGH_PREFORMANCE_PERIOD_MIN;
    }

    TLV_ADD_U16(tlv, SENSOR_DET_FSM_PERIOD_TLV, sensor_251_cfg.respond_delay_ms);

    if (sensor_251_cfg.det_range > SENSOR_251_DET_RANGE_MAX) {
        sensor_251_cfg.det_range = SENSOR_251_DET_RANGE_15M;
    }
    TLV_ADD_U8(tlv, SENSOR_251_DET_RANGE_TLV, sensor_251_det_range_tab[sensor_251_cfg.det_range]);

    if (sensor_251_cfg.high_preformance_mode) {
        TLV_ADD_U16(tlv, SENSOR_251_HIGH_PREFORMANCE_THRESH_TLV,
                        (SENSOR_THRESH_CONSTANT_PARAM - sensor_251_cfg.micro_sensitivity) * 16);

        TLV_ADD_U8(tlv, SENSOR_251_HIGH_PREFORMANCE_FILTER0_TLV,
                        (sensor_251_cfg.micro_filter > 1) ? (sensor_251_cfg.micro_filter + 1) : sensor_251_cfg.micro_filter);

    } else {
        TLV_ADD_U16(tlv, SENSOR_251_LOW_POWER_MICRO_THRESH_TLV,
                        (SENSOR_THRESH_CONSTANT_PARAM - sensor_251_cfg.micro_sensitivity) * 16);

        if (sensor_251_cfg.micro_filter > 0) {
            TLV_ADD_U8(tlv, SENSOR_251_LOW_POWER_MICRO_EN_TLV,
                            SENSOR_251_LOW_POWER_MICRO_EN_CONSTANT_PARAM | SENSOR_251_LOW_POWER_MICRO_EN);

            TLV_ADD_U8(tlv, SENSOR_251_LOW_POWER_MICRO_FILTER0_TLV, SENSOR_251_LOW_POWER_MICRO_FILTER0_PARAM);
            TLV_ADD_U8(tlv, SENSOR_251_LOW_POWER_MICRO_FILTER1_TLV, sensor_251_low_power_filter1_tab[sensor_251_cfg.micro_filter]);
            TLV_ADD_U8(tlv, SENSOR_251_LOW_POWER_MICRO_FILTER2_TLV, sensor_251_low_power_filter2_tab[sensor_251_cfg.micro_filter]);

        } else {
            TLV_ADD_U8(tlv, SENSOR_251_LOW_POWER_MICRO_EN_TLV,
                            SENSOR_251_LOW_POWER_MICRO_EN_CONSTANT_PARAM);
        }

    }

    if (sensor_251_cfg.output_en) {
        /* must be set frist */
        TLV_ADD_U8(tlv, SENSOR_OUTPUT_SEL_TLV, 0);
        TLV_ADD_U8(tlv, SENSOR_OUTPUT_EN_TLV, 1);

        /* config hold time 4 bytes offset */
        if (sensor_251_cfg.output_time_ms) {
            TLV_ADD_U16(tlv, SENSOR_OUTPUT_HOLD_TIME_TLV, sensor_251_cfg.output_time_ms / 100);
        }

        TLV_ADD_U8(tlv, SENSOR_OUTPUT_MODE_TLV,sensor_251_cfg.output_mode);
        TLV_ADD_U8(tlv, SENSOR_OUTPUT_IO_TLV, sensor_251_cfg.output_io);
        TLV_ADD_U8(tlv, SENSOR_OUTPUT_HAVE_TAGET_PRAM_TLV, sensor_251_cfg.output_have_target_pram);
        TLV_ADD_U8(tlv, SENSOR_OUTPUT_NO_TAGET_PRAM_TLV, sensor_251_cfg.output_no_target_pram);
    } else {
        /*
         * note: if the code not executed output use radar default values
         TLV_ADD_U8(tlv, SENSOR_OUTPUT_SEL_TLV, 0);
         TLV_ADD_U8(tlv, SENSOR_OUTPUT_EN_TLV, 0);
         */
    }


#if SENSOR_PRAM_DBG
    hif_debug_log("%s\n", __func__);
    sensor_param_dump(buf, tlv - buf);
#endif

    return sensor_param_send_data(buf, tlv - buf);
}

int sensor_251_work_mode_cfg(bool high_preformance_mode)
{
    sensor_251_cfg.high_preformance_mode = high_preformance_mode;
    return 0;
}

int sensor_251_micro_cfg(uint16_t sensitivity, uint8_t filter)
{
    sensor_251_cfg.micro_sensitivity = sensitivity;
    sensor_251_cfg.micro_filter      = filter;
    return 0;
}

int sensor_251_det_pram_cfg(uint16_t respond_delay_ms, uint16_t det_range, uint8_t power_back_off)
{
    sensor_251_cfg.respond_delay_ms = respond_delay_ms;
    sensor_251_cfg.det_range        = det_range;
    sensor_251_cfg.power_back_off   = power_back_off;
    return 0;
}
#endif
