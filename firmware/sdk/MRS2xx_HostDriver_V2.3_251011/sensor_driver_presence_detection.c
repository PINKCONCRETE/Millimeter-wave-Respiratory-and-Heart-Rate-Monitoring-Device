/**
 *   @file  sensor_driver.c
 *
 *   @brief
 *      APIs Implementation of Host Interface Message.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2022 Possumic, Inc.
 *
 */
#include "vendor_porting_layer.h"
#include "sensor_driver.h"

static uint16_t sensor_move_micro_det_capability_tab[] = {
    3, 6, 9, 12, 24, 48,
};

int sensor_presence_det_param_config(uint8_t det_mode, uint8_t *tlv, presence_det_t *presence_det_info)
{
    uint8_t *tlv_tmp = tlv;
    /* only config presence pram */
    if (det_mode & SENSOR_PRESENCE_EN) {
        TLV_ADD_U16(tlv_tmp,
                    SENSOR_MICRO_THRESH_TLV,
                    (SENSOR_THRESH_CONSTANT_PARAM - presence_det_info->micro_sensitivity) * 16);
        TLV_ADD_U16(tlv_tmp,
                    SENSOR_PRESENCE_THRESH_TLV,
                    (SENSOR_THRESH_CONSTANT_PARAM - presence_det_info->presence_sensitivity) * 16);

        if (presence_det_info->capability) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MICRO_DET_CAPABILITY_TLV,
                       sensor_move_micro_det_capability_tab[presence_det_info->capability - 1]);
        }

        /* for now, presence det bit0 most set 1 */
        TLV_ADD_U16(tlv_tmp, SENSOR_PRESENCE_DET_MODE_TLV, BIT(0) | presence_det_info->det_mode);

        TLV_ADD_U8(tlv_tmp, SENSOR_PRESENCE_RESPONE_TIME_TLV, presence_det_info->rsp_time);

        if (presence_det_info->micro_spectrum_interval) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MICRO_SPECTRUM_REPORT_INTERVAL_TLV, presence_det_info->micro_spectrum_interval);
        }

        if (presence_det_info->micro_spectrum_convergence_frames) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MICRO_SPECTRUM_CONVERGENCE_FRAMES_TLV, presence_det_info->micro_spectrum_convergence_frames);
        }

    }

    /* only config external pram */
    if (det_mode & SENSOR_EXTERNAL_EN) {
        /* for now, presence det only can be set 0(PIR) */
        TLV_ADD_U8(tlv_tmp, SENSOR_EXTERNAL_TYPE_SEL_TLV, 0);
        TLV_ADD_U8(tlv_tmp, SENSOR_EXTERNAL_WKIO_SEL_TLV, presence_det_info->external_io);
        TLV_ADD_U8(tlv_tmp, SENSOR_EXTERNAL_WKIO_LEVEL_TLV, presence_det_info->external_level);
    }

    return tlv_tmp - tlv;
}


