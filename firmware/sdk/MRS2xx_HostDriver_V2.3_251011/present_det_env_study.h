/*
 *   @file  present_det_env_study.h
 *
 *   @brief
 *      Header file for Host Interface Human/Micro Det Env Study Definition.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2022 Possumic, Inc.
 *
 */
#ifndef __PRESENT_DET_ENV_STUDY_H__
#define __PRESENT_DET_ENV_STUDY_H__

/* Include Files */

#ifdef __cplusplus
extern "C" {
#endif

#define SENSOR_ENV_STUDY_ENABLE   0

#define SENSOR_ENV_STUDY_MODE_NUM 2

typedef enum {
    SENSOR_ENV_STUDY_MICR_MODE = (0x01 << 0),
    SENSOR_ENV_STUDY_PRES_MODE = (0x01 << 1),
    SENSOR_ENV_STUDY_ALL_MODE  = (0x01 << 1) | (0x01 << 0),
} sensor_env_study_mode_t;

enum {
    SENSOR_ENV_STUDY_MICR_BIN = 40,
    SENSOR_ENV_STUDY_PRES_BIN = 40,
    SENSOR_ENV_STUDY_MAX_BIN  = \
            SENSOR_ENV_STUDY_MICR_BIN > SENSOR_ENV_STUDY_PRES_BIN ? \
            SENSOR_ENV_STUDY_MICR_BIN : SENSOR_ENV_STUDY_PRES_BIN,
};

#define SENSOR_ENV_STUDY_MAX_DIST \
        (SENSOR_ENV_STUDY_MICR_BIN < SENSOR_ENV_STUDY_PRES_BIN ? \
         SENSOR_ENV_STUDY_MICR_BIN : SENSOR_ENV_STUDY_PRES_BIN)

typedef struct Sensor_Env_Study_Ctx {
    uint8_t  ndist;
    uint8_t  len;
    uint8_t  cnt;
    int16_t  up_thr;
    int16_t  *buf;
} sensor_env_study_ctx_t;

typedef struct Sensor_Env_Study {
    uint8_t mode;
    uint8_t *buf;
    sensor_env_study_ctx_t **ctx;
} sensor_env_study_t;

#define SENSOR_ENV_STUDY_CTX_INIT(NDIST, UP_THR, CNT, BUF, LEN) { \
    .ndist   = (NDIST) > SENSOR_ENV_STUDY_MAX_DIST ?              \
               SENSOR_ENV_STUDY_MAX_DIST           :              \
               ((NDIST) ? (NDIST) : 1),                           \
    .up_thr  = (UP_THR),                                          \
    .cnt     = (CNT),                                             \
    .buf     = (BUF),                                             \
    .len     = (LEN) > SENSOR_ENV_STUDY_MAX_BIN ?                 \
               SENSOR_ENV_STUDY_MAX_BIN         :                 \
               ((LEN) ? (LEN) : 1),                               \
}

static inline sensor_env_study_ctx_t sensor_env_study_ctx_init(uint8_t ndist,
        int16_t up_thr, uint8_t cnt, int16_t *buf, uint8_t len) {
    return (sensor_env_study_ctx_t)SENSOR_ENV_STUDY_CTX_INIT(
            ndist,
            up_thr, cnt,
            buf,
            len);
}

#define SENSOR_ENV_STUDY_INIT(MODE, BUF, ...) {        \
    .mode = (MODE) & SENSOR_ENV_STUDY_ALL_MODE,        \
    .buf  = (BUF),                                     \
    .ctx  = (sensor_env_study_ctx_t *[]){__VA_ARGS__}, \
}

#define SENSOR_ENV_STUDY_INIT_FUNC(MODE, BUF, ...)     \
    sensor_env_study_init((MODE), (BUF),               \
            (sensor_env_study_ctx_t *[]){__VA_ARGS__}) \

int sensor_env_study(sensor_env_study_t *obj);

bool sensor_env_study_is_running(void);

static inline sensor_env_study_t sensor_env_study_init(uint8_t mode,
        uint8_t *buf, sensor_env_study_ctx_t **ctx) {
    return (sensor_env_study_t){
        .mode = (mode) & SENSOR_ENV_STUDY_ALL_MODE,
        .buf  = buf,
        .ctx  = ctx,
    };
}

#ifdef __cplusplus
}
#endif

#endif
