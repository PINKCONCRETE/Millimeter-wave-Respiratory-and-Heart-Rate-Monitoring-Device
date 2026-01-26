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

static uint16_t sensor_move_det_level_tab[] = {
    8, 16, 32, 64,
};

static uint16_t sensor_move_trac_sensitivity_tab[] = {
    1400, 1200, 1000, 800, 600, 400, 200, 100,
};

static uint16_t sensor_move_trac_level_tab[] = {
    8, 7, 6, 5, 4, 3, 2, 1,
};

int sensor_motion_det_param_config(uint8_t det_mode, uint8_t *tlv, motion_det_t *motion_det_info)
{
    uint8_t *tlv_tmp = tlv;
    /* only config micro pram */
    if (det_mode & SENSOR_MICRO_EN) {
        TLV_ADD_U8(tlv_tmp, 0x40, 0);
        TLV_ADD_U16(tlv_tmp,
                    SENSOR_MICRO_THRESH_TLV,
                    (SENSOR_THRESH_CONSTANT_PARAM - motion_det_info->sensitivity) * 16);

        if (motion_det_info->capability) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MICRO_DET_CAPABILITY_TLV,
                            sensor_move_micro_det_capability_tab[motion_det_info->capability - 1]);
        }
    }

    /* only config move pram */
    if (det_mode & SENSOR_MOVE_EN) {
        TLV_ADD_U16(tlv_tmp,
                    SENSOR_MOVE_THRESH_TLV,
                    (SENSOR_THRESH_CONSTANT_PARAM - motion_det_info->sensitivity) * 16);

        if (motion_det_info->capability) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MOVE_DET_CAPABILITY_TLV,
                            sensor_move_micro_det_capability_tab[motion_det_info->capability - 1]);
        }

        if (motion_det_info->level) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MOVE_DET_LEVEL_TLV,
                            sensor_move_det_level_tab[motion_det_info->level - 1]);
        }

        if (motion_det_info->trac_en) {
            TLV_ADD_U8(tlv_tmp, SENSOR_MOVE_TRAC_EN_TLV, 1);
            TLV_ADD_U16(tlv_tmp,
                        SENSOR_MOVE_TRAC_SENSITIVITY_TLV,
                        sensor_move_trac_sensitivity_tab[motion_det_info->trac_sensitivity]);
            TLV_ADD_U8(tlv_tmp, SENSOR_MOVE_TRAC_LEVEL_TLV,
                            sensor_move_trac_level_tab[motion_det_info->trac_level - 1]);
        }
    }

    return tlv_tmp - tlv;
}


