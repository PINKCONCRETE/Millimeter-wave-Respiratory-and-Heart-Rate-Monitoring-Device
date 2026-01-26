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
#include "present_det_env_study.h"

/* opcode */
#define HIF_PHY_SYNC_MAGIC                      0x7E
#define HIF_PHY_WKP_MAGIC                       0x55
#define HIF_PHY_ACK_MAGIC                       0x79
#define HIF_PHY_MSG_MAGIC                       0xA5

#define HIF_SENSOR_GET_TICK_CMD                 0x0
#define HIF_CHIP_RESET_CMD                      0x04
#define HIF_SENSOR_SUSPEND_CMD                  0x05
#define HIF_SENSOR_CTRL_ON_CMD                  0x07
#define HIF_SENSOR_SET_PERM_PARM_CMD            0x18
#define HIF_SENSOR_PARA_GET_CMD                 0x42
#define HIF_SENSOR_PARAM_CFG_CMD                0x60
#define HIF_SENSOR_TARGET_RANGE_GET_CMD         0x61
#define HIF_SENSOR_RANGE_SPEC_ID                0xc6
#define HIF_SENSOR_TARGET_RANGE_INFO_ID         0xc9

#define HIF_SENSOR_GET_TICK_OFFSET              0x3
#define HIF_SENSOR_DOUT_REPORT_STA_OFFSET       0x1

/*length */
#define HIF_PHY_LEN                             (sizeof(HIF_PHY_HDR))
#define HIF_HEAD_LEN                            (sizeof(HIF_MSG_HDR))
#define HIF_ACK_LEN                             (4)
#define HIF_CHECK_LEN                           (4)
#define HIF_MSG_MAX_LEN                         (1056)

#define HIF_MSG_HDR_SIZE                        (HIF_PHY_LEN + HIF_HEAD_LEN)

/*header ctrl field*/
#define HIF_MSG_FLAG_REQ_BIT                    (1U<<0)  /**< Req need a ACK to the msg      */
#define HIF_MSG_FLAG_CHECK_BIT                  (1U<<2)  /**< Message with check code        */
#define HIF_MSG_TYPE_RESERVED                   0   /**< Reserved type */
#define HIF_MSG_TYPE_TO_DEVICE                  1   /**< Message to Device */
#define HIF_MSG_TYPE_TO_HOST                    2   /**< Message to Host */
#define HIF_MSG_TYPE_LOCAL                      3   /**< Message of local data */

#define BUILD_MSG_FLAG(TYPE, FLAG)              (((TYPE) & 0x3) | ((FLAG) << 2))
#define BUILD_MSG_LENGTH(LEN, SEQ)              (((LEN) & 0xFFF) | (((SEQ) & 0x7) << 12))
#define GET_MSG_FLAG(FLAG)                      ((FLAG) >> 2)

#define HEAD_RX_PADDING                         (2)
#define HEAD_MSG_FLAG_OFFSET                    (HEAD_RX_PADDING + HIF_PHY_LEN)
#define HEAD_MSGID_OFFSET                       (HEAD_RX_PADDING + HIF_PHY_LEN + 1) // phy offset + msg id offset
#define HEAD_MSGID_LEN_OFFSET                   (HEAD_RX_PADDING + HIF_PHY_LEN + 2) //phy offset + len offset
#define HEAD_MSG_STATUS_OFFSET                  (HEAD_RX_PADDING + HIF_MSG_HDR_SIZE) // phy offset + head offset

uint8_t hif_msg_heap[HEAD_RX_PADDING + HIF_MSG_MAX_LEN];

#define HEAP_HIF_MSGID()                       (hif_msg_heap[HEAD_MSGID_OFFSET])
#define HEAP_HIF_MSG_FLAG()                    (GET_MSG_FLAG(hif_msg_heap[HEAD_MSG_FLAG_OFFSET]))
#define HEAP_HIF_MSG_STATUS()                  (hif_msg_heap[HEAD_MSG_STATUS_OFFSET])
#define HEAP_HIF_MSG_LENGTH()                  (hif_msg_heap[HEAD_MSGID_LEN_OFFSET] | ((hif_msg_heap[HEAD_MSGID_LEN_OFFSET + 1]&0xF) << 8))
#define HEAP_HIF_MSG_PHY()                     (&hif_msg_heap[HEAD_RX_PADDING])
#define HEAD_HIF_MSG_HEAD()                    (&hif_msg_heap[HEAD_MSG_FLAG_OFFSET])
#define HEAP_HIF_MSG_PAYLOAD()                 (&hif_msg_heap[HEAD_MSG_STATUS_OFFSET])
#define HEAP_HIF_MSG_SIZE()                     (HIF_MSG_HDR_SIZE + HEAP_HIF_MSG_LENGTH() + HIF_CHECK_LEN)
#define HEAP_HIF_MSG_CHKSUM32(LEN)              (hif_msg_heap[HEAD_MSG_STATUS_OFFSET + LEN] \
                                                 | (hif_msg_heap[HEAD_MSG_STATUS_OFFSET + LEN + 1] << 8) \
                                                 | (hif_msg_heap[HEAD_MSG_STATUS_OFFSET + LEN + 2] << 16) \
                                                 | (hif_msg_heap[HEAD_MSG_STATUS_OFFSET + LEN + 3] << 24))
#define HIF_CHECKSUM8(chksum)                   ((~chksum) & 0xFF)
#define HIF_CHECKSUM32(chksum)                  ((~chksum) & 0xFFFFFFFF)

#define SENSOR_SECTION_SEL_TLV						(0x20)
#define SENSOR_SECTION_EN_TLV						(0x21)

typedef struct hif_phy_hdr_t {
    uint8_t magic;      /**< magic for determine the UART header. */
    uint8_t checksum;   /**< checksum for MMW_MSG_HEADER */
} HIF_PHY_HDR;

typedef struct hif_msg_hdr_t {
    uint8_t  flag;
    uint8_t  msg_id;
    uint16_t length;
} HIF_MSG_HDR;

struct SENSOR_t {
    /* sensor driver cfg */
    HIF_INIT_CB_T init;
    HIF_WR_CB_T write;
    HIF_RD_CB_T read;
    DOUT_LEVEL_RD_T dout_read;
    HIF_RECEIVED_CB_T hif_rx_cb;
    SENSOR_TARGET_RANGE_INFO_T motion_report_cb;
    SENSOR_SYNC_TICK_ERR_T sensor_sync_tick_err_cb;
    SENSOR_MSG_ERR_CB_T sensor_msg_err_cb;
    SENSOR_RANGE_SPEC_CB_T rs_cb;
    void *motion_user_data;
    void *sync_tick_user_data;
    void *msg_err_user_data;
    uint8_t txseq;
    uint8_t  reserve[1];
    uint16_t rx_msgid;
    /* sensor cfg */
    sensor_public_ctrl_t    public_ctrl;
    sensor_info_t           info[SECTION_NUM];

} g_sensor_radar;

typedef struct __packed _rs_hdr_t {
    uint8_t  dim;
    uint16_t width: 2;
    uint16_t sign: 1;
    uint16_t fiexed_point: 5;
    uint16_t align_mode: 1;
    uint16_t dim_num;
} rs_hdr_t;

static const char *range_spec_str[] = {"mico_spectrum", "pres_spectrum"};

#define SENSOR_RANGE_SPEC_PARSE_PRINT  (0)
#define SENSOR_RANGE_SPEC_COUNT_MAX    (40)

#define RS_DEF_FMT_CHECK(dim, width, sign, fiexed_point, align_mode) \
    (dim == 1 && width == 1 && sign == 1 && fiexed_point == 6 && align_mode == 0)

static int sensor_target_range_info_cb(uint8_t *data, uint32_t size)
{
    if ((size >> 1) == 0) {
        hif_debug_log("target dispear\n");
        return 0;
    } else {
        hif_debug_log("target motion detect\n");
    }
    for (int i = 0; i < size; i += 2) {
        hif_debug_log("target[%d] range %d mm\n", i, *(uint16_t *)&data[i]);
    }
    return 0;
}

uint8_t hif_checksum8(uint8_t *data, uint32_t size)
{
    uint8_t checksum = 0;
    for (int i =  0; i < size; i++) {
        checksum += data[i];
    }
    return checksum;
}

uint32_t hif_checksum32(uint32_t *data, uint32_t size)
{
    int i;
    uint32_t checksum = 0;
    uint32_t length = size >> 2;

    for (i = 0; i < length; i++) {
        checksum += data[i];
    }

    if (size & 0x3) {
        checksum += (data[i]) & ((1 << ((size & 0x3) << 3)) - 1);
    }
    return checksum;
}

static int hif_msg_receive(uint32_t timeout_us)
{
    uint8_t  checksum8;
    uint32_t checksum32;
    bool hif_msg_err = false;
    int ret, len;
    ret = 0;
#if (CONFIG_HOST_IIC_EN)
    /* wait sensor prepara msg */
    hif_delay_us(10000);
#endif
    do {
        ret = g_sensor_radar.read(&hif_msg_heap[HEAD_RX_PADDING], 1, CFG_HIF_MAX_RX_TIMEOUT);
        if (ret == 0) {
            if (hif_msg_heap[HEAD_RX_PADDING] == HIF_PHY_MSG_MAGIC) {
                break;
            } else {
                hif_delay_us(10000);
            }
        }
    } while (timeout_us--);

    if (hif_msg_heap[HEAD_RX_PADDING] != HIF_PHY_MSG_MAGIC) {
        hif_debug_log("hif read magic error\n");
        hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HIF_MSG_HDR_SIZE);
        hif_msg_err = true;
        ret = -1;
        goto exit;
    }

    ret = g_sensor_radar.read(&hif_msg_heap[HEAD_RX_PADDING + 1], 5, CFG_HIF_MAX_RX_TIMEOUT);
    if (ret < 0) {
        hif_debug_log("hif read header error\n");
        hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HIF_MSG_HDR_SIZE);
        hif_msg_err = true;
        ret = -1;
        goto exit;
    }

    checksum8 = hif_checksum8(&hif_msg_heap[HEAD_RX_PADDING], HIF_MSG_HDR_SIZE);
    if (HIF_CHECKSUM8(checksum8) != 0) {
        hif_debug_log("check ack header checksum %x error\n", HIF_CHECKSUM8(checksum8));
        hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HIF_MSG_HDR_SIZE);
        hif_msg_err = true;
        ret = -1;
        goto exit;
    }

    len = HEAP_HIF_MSG_LENGTH();
    if (len) {
        ret = g_sensor_radar.read(HEAP_HIF_MSG_PAYLOAD(), len, CFG_HIF_MAX_RX_TIMEOUT);
        if (ret < 0) {
            hif_debug_log("hif read payload error\n");
            hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HEAP_HIF_MSG_SIZE());
            ret = -1;
            goto exit;
        }
    }

    /*check if checksum32 exist*/
    if (HEAP_HIF_MSG_FLAG() & HIF_MSG_FLAG_CHECK_BIT) {
        ret = g_sensor_radar.read(&hif_msg_heap[HEAD_MSG_STATUS_OFFSET + len], 4, CFG_HIF_MAX_RX_TIMEOUT);
        if (ret < 0) {
            hif_debug_log("hif read checksum error\n");
            hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HEAP_HIF_MSG_SIZE());
            hif_msg_err = true;
            ret = -1;
            goto exit;
        }
        checksum32 = HEAP_HIF_MSG_CHKSUM32(len);
        hif_debug_verb("checksum %x + %x\n", checksum32, hif_checksum32((uint32_t *)HEAD_HIF_MSG_HEAD(), len));
        checksum32 += hif_checksum32((uint32_t *)HEAD_HIF_MSG_HEAD(), HIF_HEAD_LEN + len);
        if (HIF_CHECKSUM32(checksum32) != 0) {
            hif_debug_log("check payload checksum %x error\n", HIF_CHECKSUM32(checksum32));
            hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HEAP_HIF_MSG_SIZE());
            hif_msg_err = true;
            ret = -1;
            goto exit;
        }
    }

    hif_verb_hexdump("rx hif msg:", &hif_msg_heap[HEAD_RX_PADDING], HEAP_HIF_MSG_SIZE());

exit:
    if (g_sensor_radar.hif_rx_cb) {
        g_sensor_radar.hif_rx_cb(hif_msg_err);
    }
    return ret;
}

static int hif_msg_send(uint8_t msg_id, uint8_t *payload, uint16_t length)
{
    int ret;
    uint32_t checksum32 = 0;
    HIF_PHY_HDR phy_hdr = {
        .magic = HIF_PHY_MSG_MAGIC,
        .checksum = 0x00,
    };

    HIF_MSG_HDR msg_hdr = {
        .flag = BUILD_MSG_FLAG(HIF_MSG_TYPE_TO_DEVICE, (HIF_MSG_FLAG_REQ_BIT | HIF_MSG_FLAG_CHECK_BIT)),
        .msg_id = msg_id,
        .length = BUILD_MSG_LENGTH(length, g_sensor_radar.txseq++),
    };

    phy_hdr.checksum  = hif_checksum8((uint8_t *)&phy_hdr, sizeof(HIF_PHY_HDR));
    phy_hdr.checksum += hif_checksum8((uint8_t *)&msg_hdr, sizeof(HIF_MSG_HDR));
    phy_hdr.checksum  = HIF_CHECKSUM8(phy_hdr.checksum);

    //send download message now
    ret = g_sensor_radar.write((uint8_t *)&phy_hdr, sizeof(HIF_PHY_HDR), 0);
    if (ret < 0) {
        hif_debug_log("cmd(%d) hif msg send phy hdr fail ret %d\n", msg_id, ret);
        goto exit;
    }

    hif_debug_verb("hif msg send:\n");
    hif_verb_segmentdump(true, (uint8_t *)&phy_hdr, sizeof(HIF_PHY_HDR));

    ret = g_sensor_radar.write((uint8_t *)&msg_hdr, sizeof(HIF_MSG_HDR), 0);
    if (ret < 0) {
        hif_debug_log("cmd(%d) hif msg send msg hdr fail ret %d\n", msg_id, ret);
        goto exit;
    }
    hif_verb_segmentdump(false, (uint8_t *)&msg_hdr, sizeof(HIF_MSG_HDR));

    ret = g_sensor_radar.write(payload, length, 0);
    if (ret < 0) {
        hif_debug_log("cmd(%d) hif msg send payload length %d fail ret %d\n", msg_id, length, ret);
        goto exit;
    }
    hif_verb_segmentdump(false, payload, length);

    checksum32 =  hif_checksum32((uint32_t *)&msg_hdr, sizeof(HIF_MSG_HDR));
    checksum32 += hif_checksum32((uint32_t *)payload, length);
    checksum32  = HIF_CHECKSUM32(checksum32);

    ret = g_sensor_radar.write((uint8_t *)&checksum32, sizeof(checksum32), 0);
    if (ret < 0) {
        hif_debug_log("cmd(%d) hif msg send checksum %d fail ret %d\n", msg_id, checksum32, ret);
        goto exit;
    }
    hif_verb_segmentdump(false, (uint8_t *)&checksum32, sizeof(checksum32));

exit:
    hif_debug_verb("\n hif msg send ret = %d\n", ret);
    return ret;
}

static int sensor_range_spec_parse(uint8_t *raw, uint16_t length)
{
    uint8_t name_len = 0;
    rs_hdr_t *hdr = (rs_hdr_t *)raw;
    uint8_t *payload = (uint8_t *)(hdr + 1);

#if SENSOR_RANGE_SPEC_PARSE_PRINT
    hif_debug_log("range spec raw: \n");
    for (int i = 0; i < length; i++)
        hif_debug_log("%02x ", raw[i]);
    hif_debug_log("\n");
#endif

    if (RS_DEF_FMT_CHECK(hdr->dim, hdr->width, hdr->sign,
                         hdr->fiexed_point, hdr->align_mode)) {
        while (name_len < (length - sizeof(rs_hdr_t))) {
            if (payload[name_len++] == '\0')
                break;
        }
        if ((name_len + sizeof(rs_hdr_t) + (hdr->dim_num * 2)) != length) {
            hif_debug_log("rs length dismatch!\n");
            return -1;
        }
        for (uint8_t path = 0; path < 2; path++) {
        if (!strncmp(payload, range_spec_str[path], name_len)) {
                if (g_sensor_radar.rs_cb)
                    g_sensor_radar.rs_cb(path + 1, (uint16_t *)(payload + name_len), hdr->dim_num);
                return 0;
            }
        }
        hif_debug_log("rs payload name dismatch\n");
    }

    return -1;
}

sensor_range_t sensor_range;

static void _hif_msg_received_callback(bool msg_err)
{
    static uint8_t sync_tick = 0;

    uint16_t msg_id = HEAP_HIF_MSGID();
    uint16_t length = HEAP_HIF_MSG_LENGTH();
    uint8_t *data = HEAP_HIF_MSG_PAYLOAD();

    if (msg_err) {
        if (g_sensor_radar.sensor_msg_err_cb) {
            g_sensor_radar.sensor_msg_err_cb(g_sensor_radar.msg_err_user_data);
        }
        hif_debug_log("sensor msg err\n");
        return;
    }

    switch (msg_id) {
    case HIF_SENSOR_TARGET_RANGE_INFO_ID:
        {
            sensor_range.target_num = length / 2;
            if (sensor_range.target_num <= SENSOR_TARGET_NUM_MAX && (sensor_range.target_buf != NULL)) {
                hif_memcpy(sensor_range.target_buf, data, length);
            }

            if (g_sensor_radar.motion_report_cb) {
                g_sensor_radar.motion_report_cb(&sensor_range, g_sensor_radar.motion_user_data);
            } else {
                sensor_target_range_info_cb(data, length);
            }
        }
        break;
    case HIF_SENSOR_GET_TICK_CMD:
        {
            uint8_t sensor_tick = data[HIF_SENSOR_GET_TICK_OFFSET];
            if (g_sensor_radar.sensor_sync_tick_err_cb) {
                if (sync_tick++ != sensor_tick) {
                    hif_debug_log("sync_tick[%d] sensor_tick[%d]\n", sync_tick, sensor_tick);
                    g_sensor_radar.sensor_sync_tick_err_cb(g_sensor_radar.sync_tick_user_data);
                    sync_tick = 0;
                    hif_msg_heap[HEAD_MSG_STATUS_OFFSET] = 0;
                    hif_msg_heap[HEAD_MSGID_OFFSET] = HIF_SENSOR_GET_TICK_CMD;
                }
            } else {
                sync_tick = 0;
            }
        }
    case HIF_SENSOR_RANGE_SPEC_ID:
        sensor_range_spec_parse(data, length);
        break;
    default:
        break;
    }

}

#if (SENSOR_MODEL_MRS261L || SENSOR_MODEL_MRS262) && (SENSOR_ENV_STUDY_ENABLE)
static void sensor_env_study_load(void)
{
    uint16_t msg_id = HEAP_HIF_MSGID();
    uint16_t length = HEAP_HIF_MSG_LENGTH();
    uint8_t *data   = HEAP_HIF_MSG_PAYLOAD();

    if (msg_id == HIF_SENSOR_RANGE_SPEC_ID) {
        SENSOR_RANGE_SPEC_CB_T cb_reg = g_sensor_radar.rs_cb;
        extern int sensor_env_study_cb(uint8_t, uint16_t *, uint16_t);
        g_sensor_radar.rs_cb = &sensor_env_study_cb;

        sensor_range_spec_parse(data, length);

        g_sensor_radar.rs_cb = cb_reg;
    }
}
#endif

static int hif_msg_ack_retry(bool ack_req, uint8_t msg_id, uint32_t timeout)
{
    int ret;
    do {
        ret = hif_msg_receive(10);
        if (ret == 0) {
            if (HEAP_HIF_MSGID() == msg_id) {
                if ((ack_req == true) && (HEAP_HIF_MSG_STATUS() != 0)) {
                    hif_debug_log("msg_id %x ack status %d error\n", msg_id, HEAP_HIF_MSG_STATUS());
                    return -1;
                }
                return 0;
            }
        }
    } while (timeout--);
    return -1;
}

int sensor_sync(uint8_t retry_cnt)
{
    int ret = -1;
    uint8_t sync_code = HIF_PHY_SYNC_MAGIC, sync_ack = 0;
    uint8_t cont_dummy_retry = CFG_CONT_DUMMY_RETRY;
    uint32_t max_dummy_retry = CFG_MAX_DUMMY_RETRY;
    do {
        ret = g_sensor_radar.write((uint8_t *)&sync_code, sizeof(sync_code), 0);
        if (ret == 0) {
            do {
                /*use do..while (ret == 0) codes to fix firmware auto send uart data out make sync hard*/
                ret = g_sensor_radar.read((uint8_t *)&sync_ack, sizeof(sync_ack), CONFIG_HIF_SYNC_TO);
                if (ret == 0) {
                    if (sync_ack == HIF_PHY_ACK_MAGIC) {
                        sync_code = HIF_PHY_WKP_MAGIC;
                        hif_delay_us(10000);
                        ret = g_sensor_radar.write((uint8_t *)&sync_code, sizeof(sync_code), 0);
                        if (ret == 0) {
                            ret = g_sensor_radar.read((uint8_t *)&sync_ack, sizeof(sync_ack), CONFIG_HIF_SYNC_TO);
                            if (ret == 0) {
                                if (sync_ack == HIF_PHY_ACK_MAGIC) {
                                    hif_debug_log("sync ack received\n");
                                    goto exit;
                                }
                            }
                        }
                    } else if (sync_ack == CFG_RX_DUMMY_MAGIC) {
                        cont_dummy_retry--;
                    } else {
                        cont_dummy_retry = CFG_CONT_DUMMY_RETRY;
                    }
                    max_dummy_retry--;
                    if ((max_dummy_retry == 0) || (cont_dummy_retry == 0)) {
                        break;
                    }
                    continue;
                }
            } while (ret == 0);
            ret = -1;
        }
        if (retry_cnt) {
            hif_debug_log("sync nack and retry remain %d\n", retry_cnt);
            hif_delay_us(10000);
        }
    } while (retry_cnt--);
exit:
    hif_debug_log("sync %d ret %d\n", retry_cnt, ret);
    return ret;
}

int sensor_wakeup(void)
{
    return sensor_sync(50);
}

int sensor_suspend(uint32_t pm_type)
{
    int ret = hif_msg_send(HIF_SENSOR_SUSPEND_CMD, (uint8_t *)&pm_type, sizeof(pm_type));
    if (ret == 0) {
        return hif_msg_ack_retry(true, HIF_SENSOR_SUSPEND_CMD, 10);
    }
    return ret;
}

int sensor_start(uint32_t on)
{
    int ret = hif_msg_send(HIF_SENSOR_CTRL_ON_CMD, (uint8_t *)&on, sizeof(on));
    if (ret == 0) {
        return hif_msg_ack_retry(true, HIF_SENSOR_CTRL_ON_CMD, 10);
    }
    return ret;
}

#if (CONFIG_FW_DOWNLOAD_SRAM)
int sensor_image_read_fw_ver(tlv_info_t *tlv_info)
{
    int ret = 0;
    uint32_t tlv_offset = fw_image_size_read();

    /* read tlv head */
    ret = fw_image_read(tlv_offset, (void *)tlv_info, sizeof(tlv_info_t));
    if ((ret != 0) || (tlv_info->magic != TLV_HEADER_MAGIC)) {
        ret = -1;
    }

    return ret;
}
#else
#define SENSOR_FLASH_IMAGE_INFO_OFFSET          0x0
#define SENSOR_FLASH_IMAGE_INFO_SIZE            (sizeof(image_info_t))
int sensor_image_read_fw_ver(tlv_info_t *tlv_info)
{
    int ret = 0;
    int cmd_ack_status_offset = 4;
    image_info_t *image_info;

    ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    struct fwdl_flash_read_cmd_t flash_read_cmd = {
        .addr = SENSOR_FLASH_IMAGE_INFO_OFFSET,
        .len  = SENSOR_FLASH_IMAGE_INFO_SIZE,
    };

    if (hif_msg_send(FW_FLASH_READ_CMD, (uint8_t *)&flash_read_cmd, sizeof(flash_read_cmd)) == 0) {
        ret = hif_msg_ack_retry(true, FW_FLASH_READ_CMD, 10);
        image_info = (image_info_t *)(HEAP_HIF_MSG_PAYLOAD() + cmd_ack_status_offset);
        if ((ret != 0) || (image_info->magic != IMAGE_HEADER_MAGIC)) {
            hif_debug_log("magic[0x%08x] image_size[%d]\n", image_info->magic, image_info->size);
            ret = -1;
        }
    }

    flash_read_cmd.addr = image_info->size;
    flash_read_cmd.len = sizeof(tlv_info_t);

    if (hif_msg_send(FW_FLASH_READ_CMD, (uint8_t *)&flash_read_cmd, sizeof(flash_read_cmd)) == 0) {
        ret = hif_msg_ack_retry(true, FW_FLASH_READ_CMD, 10);
        uint8_t *data = (HEAP_HIF_MSG_PAYLOAD() + cmd_ack_status_offset);
        memcpy(tlv_info, data, sizeof(tlv_info_t));
        if ((ret != 0) || (tlv_info->magic != TLV_HEADER_MAGIC)) {
            hif_debug_log("magic[0x%08x] fw_ver[0x%08x] cli_ver[0x%08x]\n", tlv_info->magic, tlv_info->fw_ver, tlv_info->cli_ver);
            ret = -1;
        }
    }

    return ret;
}

#endif

int sensor_set_iic_slave_addr(uint8_t addr)
{
    uint8_t perm_pram_type = 0;
    uint8_t buf[2];
    buf[0] = perm_pram_type;
    buf[1] = addr;

    if (sensor_wakeup()) {
        return -1;
    }

    int ret = hif_msg_send(HIF_SENSOR_SET_PERM_PARM_CMD, &buf[0], 2);
    if (ret == 0) {
        return hif_msg_ack_retry(false, HIF_SENSOR_SET_PERM_PARM_CMD, 10);
    }
    return ret;
}

int sensor_get_sync_tick(void)
{
    uint8_t get_ytpe = 0xFF;

    if (sensor_wakeup()) {
        return -1;
    }

    int ret = hif_msg_send(HIF_SENSOR_GET_TICK_CMD, (uint8_t *)&get_ytpe, 0);
    if (ret == 0) {
        if (hif_msg_ack_retry(true, HIF_SENSOR_GET_TICK_CMD, 10) == 0) {
                uint16_t msg_id = HEAP_HIF_MSGID();
                uint16_t length = HEAP_HIF_MSG_LENGTH();
                uint8_t *data = HEAP_HIF_MSG_PAYLOAD();
                if (msg_id == HIF_SENSOR_GET_TICK_CMD && length > HIF_SENSOR_GET_TICK_OFFSET) {
                    ret = data[HIF_SENSOR_GET_TICK_OFFSET];
                }
        }
    }

    sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("suspend sensor radar err ret %d\n", ret);
        return ret;
    }

    return ret;
}

int sensor_param_send_data(uint8_t *payload, uint16_t length)
{
    int ret = 0;
    if (length > 0) {
        ret = hif_msg_send(HIF_SENSOR_PARAM_CFG_CMD, payload, length);
        if (ret == 0) {
            return hif_msg_ack_retry(true, HIF_SENSOR_PARAM_CFG_CMD, 10);
        }
    }
    return ret;
}

int sensor_get_dout_report_sta(void)
{
    uint8_t sub_cmd = 0x01;

    if (sensor_wakeup()) {
        return -1;
    }

    int ret = hif_msg_send(HIF_SENSOR_PARA_GET_CMD, (uint8_t *)&sub_cmd, 1);
    if (ret == 0) {
        if (hif_msg_ack_retry(true, HIF_SENSOR_PARA_GET_CMD, 10) == 0) {
                uint16_t msg_id = HEAP_HIF_MSGID();
                uint16_t length = HEAP_HIF_MSG_LENGTH();
                uint8_t *data = HEAP_HIF_MSG_PAYLOAD();
                if (msg_id == HIF_SENSOR_PARA_GET_CMD && length) {
                    ret = data[HIF_SENSOR_DOUT_REPORT_STA_OFFSET];
                }
        }
    }

    sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("suspend sensor radar err ret %d\n", ret);
        return ret;
    }

    return ret;
}

sensor_range_t *sensor_get_range_obj(void)
{
    return &sensor_range;
}

#if SENSOR_PRAM_DBG
void sensor_param_dump(uint8_t *buf, uint32_t size)
{
    for (int i = 0; i < SECTION_NUM; i++) {
		hif_debug_log("section_en[%d]			[0x%02x]\n", i, g_sensor_radar.info[i].section_en);
		hif_debug_log("output_en [%d]			[0x%02x]\n", i, g_sensor_radar.info[i].output_en);
		hif_debug_log("det_mode  [%d]			[0x%02x]\n", i, g_sensor_radar.info[i].public_det.det_mode);
    }

    hif_debug_log("tlv_dump:\n");
    hif_debug_log("size:%d\n", size);
    for (int i = 0; i < size; i++) {
        if ((i % 8) == 0) {
            hif_debug_log("\n");
        }
        hif_debug_log("0x%02x ", buf[i]);
    }
    hif_debug_log("\n");
}
#endif

static uint8_t load_buf[SENSOR_TLV_BUFF_MAX];
static int sensor_load_config(void)
{
    int ret = 0;
    uint16_t config_size = 0;

    config_size = fw_image_load_tlv((uint8_t *)load_buf, SENSOR_TLV_BUFF_MAX);

    if (config_size) {
#if SENSOR_PRAM_DBG
        hif_debug_log("%s\n", __func__);
        sensor_param_dump(load_buf, config_size);
#endif

        ret = hif_msg_send(HIF_SENSOR_PARAM_CFG_CMD, load_buf, config_size);
        if (ret == 0) {
            return hif_msg_ack_retry(true, HIF_SENSOR_PARAM_CFG_CMD, 10);
        }
    }
    return ret;
}

#if (SENSOR_MODEL_MRS251 == 0) && (SENSOR_MODEL_RS2111 == 0)
int sensor_param_config(void)
{
    int ret = 0;
    int tlv_len = 0;
    uint8_t buf[256];
    uint8_t *tlv = &buf[0];
    bool is_presence = false;

    /* config pubilc upload sel 8 bytes offset*/
    TLV_ADD_U8(tlv, SENSOR_PUBLIC_UPLOAD_SEL_TLV, g_sensor_radar.public_ctrl.upload_sel);

    /* config dout and data mode 8 bytes offset*/
    TLV_ADD_U8(tlv, SENSOR_DOUT_MODE_TLV, g_sensor_radar.public_ctrl.dout_mode);
    if ((g_sensor_radar.public_ctrl.dout_mode == DOUT_DATA_MODE) && (g_sensor_radar.public_ctrl.upload_sel == PUBLIC_UPLOAD_SEL_NONE)) {
        /* dout report sel only support DOUT_DATA_MODE and PUBLIC_UPLOAD_SEL_NONE */
        TLV_ADD_U8(tlv, SENSOR_DOUT_REPORT_SEL_TLV, g_sensor_radar.public_ctrl.dout_report_sel);
    } else {
        TLV_ADD_U8(tlv, SENSOR_DOUT_REPORT_SEL_TLV, 0);
    }

    /* config api is less */
    TLV_ADD_U8(tlv, SENSOR_POWER_GAIN_TLV, g_sensor_radar.public_ctrl.power_gain_mode & 0x0F); /* bits 0~3 are valid */

    for (int i = 0; i < SECTION_NUM; i++) {
        if (g_sensor_radar.info[i].section_en) {

            /* must be set frist */
            TLV_ADD_U8(tlv, SENSOR_SECTION_SEL_TLV, g_sensor_radar.info[i].section_id);
            TLV_ADD_U8(tlv, SENSOR_SECTION_EN_TLV, 1);

            if (g_sensor_radar.info[i].public_det.range_mm >= SENSOR_DET_RANGE_MAX) {
                g_sensor_radar.info[i].public_det.range_mm = SENSOR_DET_RANGE_MAX;
            }

            TLV_ADD_U16(tlv, SENSOR_DET_RANGE_TLV, g_sensor_radar.info[i].public_det.range_mm);

            if (g_sensor_radar.info[i].public_det.det_hold_frames_cnt >= SENSOR_DET_FRAMES_HOLD_CNT_MIN) {
                TLV_ADD_U16(tlv, SENSOR_DET_FRAMES_HOLD_CNT_TLV, g_sensor_radar.info[i].public_det.det_hold_frames_cnt);
            }

            if (g_sensor_radar.info[i].public_det.period_ms >= SENSOR_DET_FSM_PERIOD_MIN) {
                TLV_ADD_U16(tlv, SENSOR_DET_FSM_PERIOD_TLV, g_sensor_radar.info[i].public_det.period_ms);
            }

            if (g_sensor_radar.info[i].public_det.det_mode) {
                uint8_t det_mode = g_sensor_radar.info[i].public_det.det_mode;
                TLV_ADD_U8(tlv, SENSOR_DET_MODE_SEL_TLV, det_mode);
                if (det_mode & (SENSOR_MICRO_EN | SENSOR_MOVE_EN)) {
                    tlv_len = sensor_motion_det_param_config(det_mode, tlv, &g_sensor_radar.info[i].motion_det);
                    if (tlv_len >= 0) {
                        tlv += tlv_len;
                    } else {
                        hif_debug_log("tlv not support!\n");
                    }

                } else if (det_mode & (SENSOR_PRESENCE_EN | SENSOR_EXTERNAL_EN)) {
#if (SENSOR_MODEL_MRS261L | SENSOR_MODEL_RS2111 | SENSOR_MODEL_MRS262 | SENSOR_MODEL_RS2111FC)
                    tlv_len = sensor_presence_det_param_config(det_mode, tlv, &g_sensor_radar.info[i].presence_det);
                    if (tlv_len >= 0) {
                        tlv += tlv_len;
                        is_presence = true;
                    } else {
                        hif_debug_log("tlv not support!\n");
                    }
#else
                    hif_debug_log("this model not support SENSOR_PRESENCE_EN/SENSOR_EXTERNAL_EN mode, check model sel please!\n");
#endif
                }

            } else {
                hif_debug_log("not sel det_mode!\n");
                return -1;
            }
        } else {
            /*
             * note: if the code not executed section use sensor default values
               TLV_ADD_U8(tlv, SENSOR_SECTION_SEL_TLV, g_sensor_radar.cfg.section_id);
               TLV_ADD_U8(tlv, SENSOR_SECTION_EN_TLV, 0);
             */
        }

        if (g_sensor_radar.info[i].output_en) {
            /* must be set frist */
            if (is_presence == true) {
                TLV_ADD_U8(tlv, SENSOR_OUTPUT_SEL_TLV, SECTION_STANDBY_ID);
            } else {
                TLV_ADD_U8(tlv, SENSOR_OUTPUT_SEL_TLV, g_sensor_radar.info[i].section_id);
            }

            TLV_ADD_U8(tlv, SENSOR_OUTPUT_EN_TLV, 1);

            /* config hold time 4 bytes offset */
            if (g_sensor_radar.info[i].output_ctrl.time_ms) {
                TLV_ADD_U16(tlv, SENSOR_OUTPUT_HOLD_TIME_TLV, g_sensor_radar.info[i].output_ctrl.time_ms / 100);
            }

            TLV_ADD_U8(tlv, SENSOR_OUTPUT_MODE_TLV, g_sensor_radar.info[i].output_ctrl.mode);
            TLV_ADD_U8(tlv, SENSOR_OUTPUT_IO_TLV, g_sensor_radar.info[i].output_ctrl.io);
            TLV_ADD_U8(tlv, SENSOR_OUTPUT_NO_TAGET_PRAM_TLV, g_sensor_radar.info[i].output_ctrl.no_target_pram);
            TLV_ADD_U8(tlv, SENSOR_OUTPUT_HAVE_TAGET_PRAM_TLV, g_sensor_radar.info[i].output_ctrl.have_target_pram);
        } else {
            /*
            * note: if the code not executed output use radar default values
            TLV_ADD_U8(tlv, SENSOR_OUTPUT_SEL_TLV, g_sensor_radar.cfg.section_id);
            TLV_ADD_U8(tlv, SENSOR_OUTPUT_EN_TLV, 0);
            */
        }
    }


#if SENSOR_PRAM_DBG
    hif_debug_log("%s line %d\n", __func__, __LINE__);
    sensor_param_dump(buf, tlv - buf);
#endif

    if ((tlv - buf) > 0) {
        ret = hif_msg_send(HIF_SENSOR_PARAM_CFG_CMD, buf, tlv - buf);
        if (ret == 0) {
            return hif_msg_ack_retry(true, HIF_SENSOR_PARAM_CFG_CMD, 10);
        }
    } else {
        hif_debug_log("tlv buffer overflow!\n");
        ret = -1;
    }

    return ret;
}

#endif

int sensor_get_target_info(void)
{
    uint8_t type = 1;
    int ret = hif_msg_send(HIF_SENSOR_TARGET_RANGE_GET_CMD, &type, sizeof(type));
    if (ret == 0) {
        return hif_msg_ack_retry(false, HIF_SENSOR_TARGET_RANGE_INFO_ID, 10);
    }
    return ret;
}

int sensor_get_rs_micro_info(void)
{
    uint8_t type = 2;
    int ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    ret = hif_msg_send(HIF_SENSOR_TARGET_RANGE_GET_CMD, &type, sizeof(type));
    if (ret == 0) {
        ret = hif_msg_ack_retry(false, HIF_SENSOR_RANGE_SPEC_ID, 10);
#if (SENSOR_MODEL_MRS261L || SENSOR_MODEL_MRS262) && (SENSOR_ENV_STUDY_ENABLE)
        if (sensor_env_study_is_running()) {
            sensor_env_study_load();
        }
#endif
        return ret;
    }

    sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("suspend sensor radar err ret %d\n", ret);
        return ret;
    }
    return ret;
}

int sensor_get_rs_presence_info(void)
{
    uint8_t type = 3;
    int ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    ret = hif_msg_send(HIF_SENSOR_TARGET_RANGE_GET_CMD, &type, sizeof(type));
    if (ret == 0) {
        ret = hif_msg_ack_retry(false, HIF_SENSOR_RANGE_SPEC_ID, 10);
#if (SENSOR_MODEL_MRS261L || SENSOR_MODEL_MRS262) && (SENSOR_ENV_STUDY_ENABLE)
        if (sensor_env_study_is_running()) {
            sensor_env_study_load();
        }
#endif
        return ret;
    }

    sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("suspend sensor radar err ret %d\n", ret);
        return ret;
    }
    return ret;
}


int sensor_read_target_range_info(void)
{
    int ret;
    if (g_sensor_radar.public_ctrl.upload_sel & SENSOR_PUBLIC_UPLOAD_SEL_MSK) {
        ret = sensor_get_target_info();
        if (ret < 0) {
            hif_debug_log("poll get target info fail\n");
        }
        return ret;
    } else {
        hif_msg_ack_retry(false, HIF_SENSOR_TARGET_RANGE_INFO_ID, 10);
    }
    return 0;
}

int sensor_wakeup_read_and_suspend(void)
{
    int ret = 0;

    ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    ret = sensor_get_target_info();
    if (ret < 0) {
        hif_debug_log("poll get target info fail\n");
    }

    sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("suspend sensor radar err ret %d\n", ret);
        return ret;
    }
    return 0;
}

int sensor_report_process(void)
{
#if (SENSOR_MODEL_MRS251 == 0) && (SENSOR_MODEL_RS2111 == 0)
    int report_sta = 0;
    int ret = 0;

    report_sta = sensor_get_dout_report_sta();
    hif_debug_log("get report sta 0x%02x\n", report_sta);

    ret = sensor_wakeup_read_and_suspend();
    if (ret) {
        return ret;
    }

#if (CONFIG_HOST_IIC_EN == 0)
    hif_delay_us(50000);
#endif

    if (report_sta & DOUT_REPORT_SEL_MICRO) {
        ret = sensor_get_rs_micro_info();
        if (ret) {
            return ret;
        }
    }

#if (CONFIG_HOST_IIC_EN == 0)
    hif_delay_us(50000);
#endif

    if (report_sta & DOUT_REPORT_SEL_PRES) {
        ret = sensor_get_rs_presence_info();
        if (ret) {
            return ret;
        }
    }


#if (CONFIG_HOST_IIC_EN == 0)
    hif_delay_us(50000);
#endif

#endif
    return 0;
}

static int sensor_dout_level_cb(uint8_t level, bool sync)
{
    int ret = 0;
    bool active = !!level;

    if (g_sensor_radar.public_ctrl.upload_sel) {
        while (active) {
            sensor_report_process();
            hif_delay_us(3);
            active = !!g_sensor_radar.dout_read();
        };
    } else {
        if (active) {
            hif_debug_log("led turn on\n");
#if (CFG_DOUT_CTRL_MODE_READ_TARGET_INFO_ENA)
            ret = sensor_report_process();
            if (ret < 0) {
                hif_debug_log("dout ctrl mode read range info fail\n");
            }
#endif
        } else {
            hif_debug_log("led turn off\n");
        }
    }
    return ret;
}

int sensor_start_motion_det(void)
{
    int ret;
    ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    ret = sensor_load_config();

    if (ret < 0) {
        hif_debug_log("load sensor radar param err ret %d\n", ret);
        return ret;
    }
    ret = sensor_start(true);
    if (ret < 0) {
        hif_debug_log("start sensor radar err ret %d\n", ret);
        return ret;
    }
    return 0;
}

int sensor_start_motion_cfg(void)
{
    int ret;
    ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    ret = sensor_param_config();

    if (ret < 0) {
        hif_debug_log("config sensor radar param err ret %d\n", ret);
        return ret;
    }
    ret = sensor_start(true);
    if (ret < 0) {
        hif_debug_log("start sensor radar err ret %d\n", ret);
        return ret;
    }
    return 0;
}


int sensor_stop_motion_det(void)
{
    int ret;
    ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }
    ret = sensor_start(false);
    if (ret < 0) {
        hif_debug_log("stop sensor radar err ret %d\n", ret);
        return ret;
    }
    return 0;
}

int sensor_main_loop_run(bool sync)
{
    static uint8_t dout_level = 0;
    uint8_t dout_cur_level;

    if (sync) {
        sensor_get_sync_tick();
    }

    if (g_sensor_radar.dout_read) {
        dout_cur_level = g_sensor_radar.dout_read();
        if (dout_cur_level != dout_level) {
            hif_debug_log("dout level change to %d\n", dout_cur_level);
            sensor_dout_level_cb(dout_cur_level, sync);
            dout_level = g_sensor_radar.dout_read();
        }
        while (g_sensor_radar.public_ctrl.dout_mode == DOUT_DATA_MODE) {
            dout_cur_level = g_sensor_radar.dout_read();
            if (dout_cur_level) {
                hif_debug_log("dout level high for data mode\n");
                sensor_dout_level_cb(dout_cur_level, sync);
            } else {
                break;
            }
        }
    }

    return 0;
}

void sensor_cfg_get(sensor_info_t *info)
{
    if (info) {
        hif_memcpy(info, &g_sensor_radar.info, sizeof(sensor_info_t) * SECTION_NUM);
    }
}

void sensor_cfg_set(sensor_info_t *info)
{
    if (info) {
        hif_memcpy(&g_sensor_radar.info, info, sizeof(sensor_info_t) * SECTION_NUM);
    }
}

void sensor_intf_register(HIF_INIT_CB_T init_cb, HIF_WR_CB_T write_cb, HIF_RD_CB_T read_cb, DOUT_LEVEL_RD_T dout_read_cb)
{
    g_sensor_radar.init = init_cb;
    g_sensor_radar.write = write_cb;
    g_sensor_radar.read = read_cb;
    g_sensor_radar.dout_read = dout_read_cb;
}

void sensor_range_info_report_register(SENSOR_TARGET_RANGE_INFO_T report_cb, void *user_data)
{
    g_sensor_radar.motion_report_cb = report_cb;
    g_sensor_radar.motion_user_data = user_data;
}

void sensor_sync_tick_report_register(SENSOR_SYNC_TICK_ERR_T report_cb, void *user_data)
{
    g_sensor_radar.sensor_sync_tick_err_cb = report_cb;
    g_sensor_radar.sync_tick_user_data = user_data;
}

void sensor_msg_err_report_register(SENSOR_MSG_ERR_CB_T report_cb, void *user_data)
{
    g_sensor_radar.sensor_msg_err_cb = report_cb;
    g_sensor_radar.msg_err_user_data = user_data;
}

void sensor_rs_report_register(SENSOR_RANGE_SPEC_CB_T report_cb)
{
    g_sensor_radar.rs_cb = report_cb;
}

int sensor_init(void)
{
    int ret = 0;
    /* clr cfg */
    memset((uint8_t *)&g_sensor_radar.info, 0, sizeof(g_sensor_radar.info));
    if (g_sensor_radar.init) {
        ret = g_sensor_radar.init();
    }
    g_sensor_radar.hif_rx_cb                        = &_hif_msg_received_callback;
    g_sensor_radar.txseq                            = 0;
    g_sensor_radar.rx_msgid                         = 0;
    g_sensor_radar.public_ctrl.upload_sel           = PUBLIC_UPLOAD_SEL_NONE;   /* close all upload */
    g_sensor_radar.public_ctrl.dout_mode            = DOUT_CTRL_MODE;           /* dout mode set DOUT_CTRL_MODE */
    g_sensor_radar.public_ctrl.dout_report_sel      = DOUT_REPORT_SEL_NONE;     /* close dout report */
    return ret;
}

int sensor_multi_pram_cfg(void)
{
    g_sensor_radar.info[SECTION_STANDBY_ID].public_det.det_mode         |= SENSOR_MICRO_EN;
    g_sensor_radar.info[SECTION_STANDBY_ID].section_id                  = SECTION_STANDBY_ID;
    g_sensor_radar.info[SECTION_STANDBY_ID].section_en                  = true;
    g_sensor_radar.info[SECTION_STANDBY_ID].public_det.range_mm         = 3250;
    g_sensor_radar.info[SECTION_STANDBY_ID].public_det.period_ms        = 333;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.sensitivity      = 18;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.level            = 1;

    g_sensor_radar.info[SECTION_STANDBY_ID].public_det.det_mode         |= SENSOR_MOVE_EN;
    g_sensor_radar.info[SECTION_STANDBY_ID].section_id                  = SECTION_DETECTION_ID;
    g_sensor_radar.info[SECTION_STANDBY_ID].section_en                  = true;
    g_sensor_radar.info[SECTION_STANDBY_ID].public_det.range_mm         = 1000;
    g_sensor_radar.info[SECTION_STANDBY_ID].public_det.period_ms        = 250;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.sensitivity      = 23;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.level            = 3;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.trac_en          = true;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.trac_level       = 3;
    g_sensor_radar.info[SECTION_STANDBY_ID].motion_det.trac_sensitivity = 5;

    g_sensor_radar.public_ctrl.upload_sel                               = PUBLIC_UPLOAD_SEL_NONE;   /* close all upload */
    g_sensor_radar.public_ctrl.dout_mode                                = DOUT_CTRL_MODE;           /* dout mode set DOUT_CTRL_MODE */
    g_sensor_radar.public_ctrl.dout_report_sel                          = DOUT_REPORT_SEL_NONE;     /* close dout report */

    return 0;
}

int sensor_startup(void)
{
    int ret;
    ret = sensor_init();
    if (ret < 0) {
        hif_debug_log("sensor radar init fail %d\n", ret);
    }

    ret = sensor_stop_motion_det();
    if (ret < 0) {
        hif_debug_log("sensor radar stop motion detect fail %d\n", ret);
        goto exit;
    }
    hif_debug_log("motion detect stop success\n");

    ret = sensor_start_motion_det();
    if (ret < 0) {
        hif_debug_log("sensor radar start motion detect fail %d\n", ret);
        goto exit;
    } else {
        /* wait for default pram run done*/
        hif_delay_us(500000);
    }

    hif_debug_log("motion detect start success\n");


    ret = sensor_wakeup();

exit:
    return ret;
}

int sensor_pram_cfg_startup(void)
{
    int ret;
    ret = sensor_stop_motion_det();
    if (ret < 0) {
        hif_debug_log("sensor radar stop motion detect fail %d\n", ret);
        goto exit;
    }
    hif_debug_log("motion detect stop success\n");

    ret = sensor_start_motion_cfg();
    if (ret < 0) {
        hif_debug_log("sensor radar start motion detect fail %d\n", ret);
        goto exit;
    }
    hif_debug_log("motion detect start success\n");
exit:
    ret = sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("sensor radar start motion detect fail %d\n", ret);
        goto exit;
    }
    hif_debug_log("sensor radar device fall into lowpower mode\n");
    return ret;
}

int sensor_public_cfg(uint8_t public_upload_sel, uint8_t dout_mode, uint8_t dout_report_sel)
{
    if (public_upload_sel & (dout_mode == DOUT_CTRL_MODE)) {
        hif_debug_log(" not support active upload in DOUT_CTRL_MODE \n");
        return -1;
    }

    g_sensor_radar.public_ctrl.upload_sel                       = public_upload_sel & SENSOR_PUBLIC_UPLOAD_SEL_MSK;
    g_sensor_radar.public_ctrl.dout_mode                        = dout_mode;
    g_sensor_radar.public_ctrl.dout_report_sel                  = dout_report_sel & SENSOR_DOUT_REPORT_SEL_MSK;

    return 0;
}

int sensor_range_cfg(uint8_t cfg_id, uint16_t range_mm)
{
    if (cfg_id >= SECTION_NUM) {
        hif_debug_log("cfg_id not support\n");
        return -1;
    }

    g_sensor_radar.info[cfg_id].section_id          = cfg_id;
    g_sensor_radar.info[cfg_id].section_en          = true;
    g_sensor_radar.info[cfg_id].public_det.range_mm = range_mm;

    return 0;
}

int sensor_detection_mode_cfg(uint8_t cfg_id, uint8_t det_mode, uint16_t pram, uint16_t extra_pram)
{
    if (cfg_id >= SECTION_NUM) {
        hif_debug_log("cfg_id not support\n");
        return -1;
    }

    g_sensor_radar.info[cfg_id].section_id                              = cfg_id;
    g_sensor_radar.info[cfg_id].section_en                              = cfg_id;
    g_sensor_radar.info[cfg_id].public_det.det_mode                     = det_mode;

    if (det_mode & (SENSOR_MICRO_EN | SENSOR_MOVE_EN)) {
        g_sensor_radar.info[cfg_id].motion_det.sensitivity              = pram;
    } else if (det_mode & SENSOR_PRESENCE_EN) {
        g_sensor_radar.info[cfg_id].presence_det.micro_sensitivity      = pram;
        g_sensor_radar.info[cfg_id].presence_det.presence_sensitivity   = extra_pram;
    } else if (det_mode & SENSOR_EXTERNAL_EN) {
        g_sensor_radar.info[cfg_id].presence_det.external_io            = pram;
        g_sensor_radar.info[cfg_id].presence_det.external_level         = extra_pram;
    }

    return 0;
}

int sensor_period_cfg(uint8_t cfg_id, uint16_t period_ms)
{
    if (cfg_id >= SECTION_NUM) {
        hif_debug_log("cfg_id not support\n");
        return -1;
    }

    g_sensor_radar.info[cfg_id].section_id                  = cfg_id;
    g_sensor_radar.info[cfg_id].section_en                  = true;
    g_sensor_radar.info[cfg_id].public_det.period_ms        = period_ms;

    return 0;
}

int sensor_range_spec_threshold_cfg(uint8_t path, uint8_t *thr, uint16_t count)
{
    int ret = 0;
    uint8_t buf[128];
    uint8_t *tlv = &buf[0];

    if (path < SENSOR_RANGE_SPEC_MMOTION || path > SENSOR_RANGE_SPEC_PRES ||
        count > SENSOR_RANGE_SPEC_COUNT_MAX) {
        hif_debug_log("threshold_cfg invalid param, %d, %d\n", path, count);
        return -1;
    }

    ret = sensor_wakeup();
    if (ret < 0) {
        hif_debug_log("wakeup sensor radar err ret %d\n", ret);
        return ret;
    }

    *tlv++ = SENSOR_RANGE_SPEC_THR_TLV;
    *tlv++ = count + 1;
    *tlv++ = path;
    memcpy(tlv, thr, count);
    ret = hif_msg_send(HIF_SENSOR_PARAM_CFG_CMD, buf, tlv - buf + count);
    if (ret == 0) {
        printk("sensor_range_spec_threshold_cfg\n");
        ret = hif_msg_ack_retry(true, HIF_SENSOR_PARAM_CFG_CMD, 10);
    }

    ret = sensor_suspend(2);
    if (ret < 0) {
        hif_debug_log("suspend sensor radar fail ret %d\n", ret);
        return ret;
    }

    return ret;
}
