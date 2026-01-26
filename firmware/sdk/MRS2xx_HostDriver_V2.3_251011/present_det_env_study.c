#include "vendor_porting_layer.h"
#include "sensor_driver.h"
#include "present_det_env_study.h"

static sensor_env_study_t *ses;

#define SENSOR_ENV_STUDY_DEBUG 1

bool sensor_env_study_is_running(void)
{
    return ses ? (ses->mode ? true : false) : false;
}

static int sensor_env_study_proc(uint8_t path, uint8_t mode, int16_t *data,
        sensor_env_study_ctx_t *ctx);

int sensor_env_study_cb(uint8_t path, uint16_t *data, uint16_t len);

int sensor_env_study(sensor_env_study_t *obj)
{
    int ret = 0;

    // deal with error and init
    if (!obj) {
        ret = -1;
        goto err;
    }

    ses = obj;

    for (int i = 0; i < SENSOR_ENV_STUDY_MODE_NUM; i++) {
        uint8_t mode_mask = (0x01 << i);
        if ((ses->mode & mode_mask) && (ses->ctx[i])) {
            sensor_env_study_ctx_t *ctx = ses->ctx[i];

            if (ctx->ndist > ctx->len) {
                ses->mode = 0;
                ret = -2;
                goto err;
            }

            if (ctx->buf) {
                hif_memset(ctx->buf, 0, sizeof(int16_t) * ctx->len);
                continue;
            }
        }
        ses->mode &= ~mode_mask;
    }

    if (!ses->mode) {
        ret = -3;
        goto err;
    }

    // PORT NOTE: check if the parameter need change
    sensor_public_cfg(0, 1, (ses->mode << 2));
    ret = sensor_pram_cfg_startup();
    if (!ret) {
        goto exit;
    }

    hif_debug_log("[ERR]%s: startup fail\n", __func__);
err:
    hif_debug_log("[ERR]%s: %d\n", __func__, ret);
exit:
    return ret;
}

static int sensor_env_study_proc(uint8_t path, uint8_t mode, int16_t *data,
        sensor_env_study_ctx_t *ctx)
{
    // init
    data[1] = data[1] > data[0] ? data[1] : data[0];
    // update peak
    int16_t *data_ptr = data + 1;
    int16_t *data_end = data + ctx->len;

    int16_t *buf_ptr = ctx->buf + 1;
    int16_t *buf_end = ctx->buf + ctx->len;

    for (; buf_ptr < buf_end; buf_ptr += ctx->ndist) {
        int16_t *dptr_step = data_ptr + ctx->ndist;
        int16_t *dptr_end  = dptr_step > data_end ? data_end : dptr_step;
        int16_t  max       = *data_ptr++;
        for (; data_ptr < dptr_end; data_ptr++) {
            max = max > data_ptr[0] ? max : data_ptr[0];
        }

        buf_ptr[0] = max > buf_ptr[0] ? max : buf_ptr[0];
    }

#if (SENSOR_ENV_STUDY_DEBUG == 1)
        hif_debug_log("Peak[%d]%d:%d: ", path, ctx->cnt, ses->mode);
        for (int j = 1; j < ctx->len; j += ctx->ndist) {
            hif_debug_log("[%d]:%d ", j, ctx->buf[j]);
        }
        hif_debug_log("\n");
#endif

    // end study callback
    if (--ctx->cnt == 0) {
        // calculate up threshold and data format
        buf_ptr = ctx->buf + 1;
        uint8_t *res_ptr = ses->buf + 1;
        uint8_t *res_end = ses->buf + ctx->len;
        for (; res_ptr < res_end ; res_ptr += ctx->ndist) {
            res_ptr[0] = (uint8_t)((buf_ptr[0] + ctx->up_thr) >> 5);
            buf_ptr   += ctx->ndist;
        }

        // fill up
        ses->buf[0] = ses->buf[1];
        uint8_t *res_value = ses->buf + 1;
        uint8_t *rptr_end;
        for (; res_value < res_end; res_value = rptr_end) {
            uint8_t *res_step = res_value + ctx->ndist;
            rptr_end = res_step > res_end ? res_end : res_step;
            res_ptr  = res_value + 1;
            for (; res_ptr < rptr_end; res_ptr++) {
                res_ptr[0] = res_value[0];
            }
        }

#if (SENSOR_ENV_STUDY_DEBUG == 1)
        hif_debug_log("Res: ");
        for (int j = 0; j < ctx->len; j++) {
            hif_debug_log("%d ", ses->buf[j]);
        }
        hif_debug_log("\n");
#endif

        int ret = sensor_range_spec_threshold_cfg(path, ses->buf, ctx->len);
        if (ret) {
            hif_debug_log("[ERR]%s: dl thr cfg %d\n", __func__, ret);
            return ret;
        }

        // PORT NOTE: check if the parameter need change
        sensor_public_cfg(0, 1, ((ses->mode & (~mode)) << 2));
        ret = sensor_pram_cfg_startup();
        if (ret) {
            hif_debug_log("[ERR]%s: startup\n", __func__);
            return ret;
        }

        ses->mode &= ~mode;
    }
    return 0;
}

int sensor_env_study_cb(uint8_t path, uint16_t *data, uint16_t len)
{
    int ret = 0;
    // deal with err
    if (data == NULL) {
        ret = -1;
        goto err;
    }

    // adaptive proc
    for (uint8_t i = 0; i < SENSOR_ENV_STUDY_MODE_NUM; i++) {
        uint8_t mode_mask = (0x01 << i);
        if ((path - 1 == i) && (ses->mode & mode_mask)) {
            sensor_env_study_ctx_t *ctx = ses->ctx[i];
            if (ctx->len <= len) {
                ret = sensor_env_study_proc(path, mode_mask, data, ctx);
            } else {
                // (unlikely) hif communication error
                ret = -2;
                hif_debug_log("[ERR]%s: communication\n", __func__);
            }
        }
    }

    if (ret) {
        ses->mode = 0;
    }

    // not the wanted spectrum, continue
    if (ses->mode) {
        return 0;
    }

    // end up env study
    ses = NULL;

    // dout set state mode
    sensor_public_cfg(0, 0, 0);
    ret = sensor_pram_cfg_startup();
    if (!ret) {
        goto exit;
    }

    hif_debug_log("[ERR]%s: startup\n", __func__);
err:
    hif_debug_log("[ERR]%s: %d\n", __func__, ret);
exit:
    return ret;
}
