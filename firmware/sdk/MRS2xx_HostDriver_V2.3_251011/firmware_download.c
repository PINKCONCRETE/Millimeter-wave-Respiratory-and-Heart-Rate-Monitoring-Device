/**
 *   @file  firmware_download.c
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
#include "firmware_download.h"

#define CONFIG_HIF_PROTO_VERSION                       0x03
#define CONFIG_FW_BEFORE_1013                          0x0

#define HIF_PHY_SYNC_MAGIC                      0x7E
#define HIF_PHY_WKP_MAGIC                       0x55
#define HIF_PHY_ACK_MAGIC                       0x79
#define HIF_PHY_MSG_MAGIC                       0xA5

#define HIF_PHY_LEN                             (sizeof(HIF_PHY_HDR))
#define HIF_HEAD_LEN                            (sizeof(HIF_MSG_HDR))
#define HIF_ACK_LEN                             (4)
#define HIF_CHECK_LEN                           (4)
#define HIF_MSG_MAX_LEN                         (0x420)

#define HIF_MSG_FLAG_REQ_BIT                    (1U<<0)  /**< Req need a ACK to the msg      */
#define HIF_MSG_FLAG_CHECK_BIT                  (1U<<2)  /**< Message with check code        */
#define HIF_MSG_TYPE_RESERVED                   0   /**< Reserved type */
#define HIF_MSG_TYPE_TO_DEVICE                  1   /**< Message to Device */
#define HIF_MSG_TYPE_TO_HOST                    2   /**< Message to Host */
#define HIF_MSG_TYPE_LOCAL                      3   /**< Message of local data */

#define BUILD_MSG_FLAG(TYPE, FLAG)              (((TYPE) & 0x3) | ((FLAG) << 2))
#define BUILD_MSG_LENGTH(LEN, SEQ)              (((LEN) & 0xFFF) | (((SEQ) & 0x7) << 12))

#define FWDL_ACK_HDR_SIZE                      (HIF_PHY_LEN + HIF_HEAD_LEN)
#define FWDL_ACK_PLD_SIZE                      (HIF_HEAD_LEN + HIF_ACK_LEN + HIF_CHECK_LEN)
#define FWDL_ACK_TOTAL_SIZE                    (HIF_PHY_LEN + FWDL_ACK_PLD_SIZE)
#define FWDL_ACK_STATUS_OFFSET                 (HIF_PHY_LEN + HIF_HEAD_LEN)

typedef struct hif_phy_hdr_t {
    uint8_t magic;      /**< magic for determine the UART header. */
    uint8_t checksum;   /**< checksum for MMW_MSG_HEADER */
#if (CONFIG_HIF_PROTO_VERSION == 0x02)
    uint16_t padding;
#endif
} HIF_PHY_HDR;

typedef struct hif_msg_hdr_t {
    uint8_t  flag;
    uint8_t  msg_id;
    uint16_t length;
} HIF_MSG_HDR;

struct fw_download_t {
    FWDL_INIT_CB_T init;
    FWDL_WR_CB_T write;
    FWDL_RD_CB_T read;
    FWDL_IMAGE_READ_CB_T image_read;
    uint8_t txseq;
    uint8_t reserved[3];
} g_fw_download;

#if (!CONFIG_SAVE_MEMORY_ENA)
struct hif_msg_header_t {
    uint8_t  magic;
    uint8_t  checksum;
    uint16_t biref;
    uint8_t  flag;
    uint8_t  cmd_id;
    uint16_t length;
};
uint8_t hif_msg_heap[HIF_MSG_MAX_LEN];
#endif

uint8_t fwdl_checksum8(uint8_t *data, uint32_t size)
{
    uint8_t checksum = 0;
    for (int i =  0; i < size; i++) {
        checksum += data[i];
    }
    return ~checksum;
}

uint32_t fwdl_checksum32(uint32_t *data, uint32_t size)
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
    return ~checksum;
}

static int fwdl_receive_ack_msg(uint32_t timeout_us)
{
    bool ack_received = false;
    int ret, i, retry = CONFIG_FWDL_ACK_RETRY_CNT;
    uint8_t fwdl_ack_buf[FWDL_ACK_TOTAL_SIZE];
    uint16_t length;
    uint32_t checksum = 0;

#if (CONFIG_HOST_IIC_EN)
    /* wait sensor prepara msg */
    hif_delay_us(10000);
#endif

    do {
        hif_debug_verb("wait fwdl ack size %d\n", FWDL_ACK_TOTAL_SIZE);
        ret = g_fw_download.read(&fwdl_ack_buf[0], FWDL_ACK_TOTAL_SIZE, timeout_us);
        if (ret < 0) {
            hif_debug_log("read fwdl ack error ret %d\n", ret);
            goto exit;
        }
        for (i = 0; i < FWDL_ACK_TOTAL_SIZE; i++) {
            if (fwdl_ack_buf[i] == HIF_PHY_MSG_MAGIC) {
                hif_debug_verb("received ack magic\n");
                if (i != 0) {
                    hif_memcpy(&fwdl_ack_buf[0], &fwdl_ack_buf[i], FWDL_ACK_TOTAL_SIZE - i);
                    ret = g_fw_download.read(&fwdl_ack_buf[FWDL_ACK_TOTAL_SIZE - i], i, timeout_us);
                    if (ret < 0) {
                        hif_debug_log("read ack remain size %d fail %d\n", FWDL_ACK_TOTAL_SIZE - i, ret);
                        goto exit;
                    }
                }
                ack_received = true;
                break;
            }
        }
        if (ack_received == true) {
            break;
        }
        hif_debug_log("received no ack msg and loop to read again\n");
        hif_delay_us(CONFIG_WAIT_ACK_PENDING_TIME);
    } while (retry--);

    if (ack_received == false) {
        hif_debug_log("receive ack retry %d timeout %d fail\n", CONFIG_FWDL_ACK_RETRY_CNT, timeout_us);
        return -1;
    }

    // receice ack msg done and check if the fwdl ack corrected.
    ret = fwdl_checksum8(&fwdl_ack_buf[0], FWDL_ACK_HDR_SIZE);
    if (ret != 0) {
        hif_debug_log("check ack header checksum %x error\n", ret);
        goto exit;
    }

    //check if ack is correct or not
    if (fwdl_ack_buf[FWDL_ACK_STATUS_OFFSET] != 0) {
        ret = -1;
        hif_debug_log("check ack status code %d error\n", fwdl_ack_buf[8]);
        goto exit;
    }

    hif_memcpy(&fwdl_ack_buf[0], &fwdl_ack_buf[HIF_PHY_LEN], FWDL_ACK_PLD_SIZE);
    checksum = fwdl_checksum32((uint32_t *)&fwdl_ack_buf[0], FWDL_ACK_PLD_SIZE);
    length = (fwdl_ack_buf[2] + ((fwdl_ack_buf[3] &0xF) << 8));
    if (length > HIF_ACK_LEN) {
        length -= HIF_ACK_LEN;
        hif_debug_log("warning for more data remain to read len %d\n", length);
        do {
            i = HIF_MIN(FWDL_ACK_PLD_SIZE, length);
            ret = g_fw_download.read((uint8_t *)&fwdl_ack_buf[0], 4, timeout_us);
            if (ret < 0) {
                hif_debug_log("read dummy size %d fail ret = %d\n", length, ret);
                goto exit;
            }
            checksum = ~((~checksum) + ~fwdl_checksum32((uint32_t *)&fwdl_ack_buf[0], i));
            length -= i;
        } while (length);
    }
    if (checksum) {
        hif_debug_log("check ack payload checksum %x error\n", checksum);
        ret = -1;
    }

exit:
    return ret;
}

#if (CONFIG_SAVE_MEMORY_ENA)
int fwdl_send_hif_msg(uint8_t cmd_id, uint8_t *payload, uint16_t length)
{
	int ret;
	uint32_t checksum32;
	HIF_PHY_HDR phy_hdr = {
		.magic = HIF_PHY_MSG_MAGIC,
		.checksum = 0x00,
#if (CONFIG_HIF_PROTO_VERSION == 0x02)
		.padding = 0x00,
#endif
	};

	HIF_MSG_HDR msg_hdr = {
		.flag = BUILD_MSG_FLAG(HIF_MSG_TYPE_TO_DEVICE, (HIF_MSG_FLAG_REQ_BIT | HIF_MSG_FLAG_CHECK_BIT)),
		.msg_id = cmd_id,
		.length = BUILD_MSG_LENGTH(length, g_fw_download.txseq++),
	};

	phy_hdr.checksum = ~((~fwdl_checksum8((uint8_t *)&phy_hdr, sizeof(HIF_PHY_HDR))) +
							 (~fwdl_checksum8((uint8_t *)&msg_hdr, sizeof(HIF_MSG_HDR))));

	//send download message now
	ret = g_fw_download.write((uint8_t *)&phy_hdr, sizeof(HIF_PHY_HDR), 0);
	if (ret < 0) {
		hif_debug_log("cmd(%d) fwdl send phy_hdr fail ret %d\n", cmd_id, ret);
		goto exit;
	}

	ret = g_fw_download.write((uint8_t *)&msg_hdr, sizeof(HIF_MSG_HDR), 0);
	if (ret < 0) {
		hif_debug_log("cmd(%d) fwdl send msg_hdr fail ret %d\n", cmd_id, ret);
		goto exit;
	}

#if (CONFIG_HIF_PROTO_VERSION == 0x02)
	ret = g_fw_download.write(payload, (length + 3)&(~0x3), 0);
	if (ret < 0) {
		hif_debug_log("cmd(%d) fwdl send payload length %d fail ret %d\n", cmd_id, length, ret);
		goto exit;
	}
#else
	ret = g_fw_download.write(payload, length, 0);
	if (ret < 0) {
		hif_debug_log("cmd(%d) fwdl send payload length %d fail ret %d\n", cmd_id, length, ret);
		goto exit;
	}
#endif

	checksum32 = ~((~fwdl_checksum32((uint32_t *)&msg_hdr, sizeof(HIF_MSG_HDR))) +
	                (~fwdl_checksum32((uint32_t *)payload, length)));
	ret = g_fw_download.write((uint8_t *)&checksum32, sizeof(checksum32), 0);
	if (ret < 0) {
		hif_debug_log("cmd(%d) fwdl send checksum %d fail ret %d\n", cmd_id, checksum32, ret);
		goto exit;
	}

	//received ack msg
	ret = fwdl_receive_ack_msg(CONFIG_FWDL_ACK_TIMEOUT);
	if (ret < 0) {
		hif_debug_log("fwdl transfer receive ack fail\n");
	}

exit:
	hif_debug_verb("fwdl transfer end ret = %d\n", ret);
	return ret;

}
#else
int fwdl_send_hif_msg(uint8_t cmd_id, uint8_t *payload, uint16_t length)
{
    int ret;
    uint16_t size = 0;
    uint32_t checksum32 = 0;
    HIF_PHY_HDR phy_hdr = {
        .magic = HIF_PHY_MSG_MAGIC,
        .checksum = 0x00,
#if (CONFIG_HIF_PROTO_VERSION == 0x02)
        .padding = 0x00,
#endif
    };

    HIF_MSG_HDR msg_hdr = {
        .flag = BUILD_MSG_FLAG(HIF_MSG_TYPE_TO_DEVICE, (HIF_MSG_FLAG_REQ_BIT | HIF_MSG_FLAG_CHECK_BIT)),
        .msg_id = cmd_id,
        .length = BUILD_MSG_LENGTH(length, g_fw_download.txseq++),
    };

    phy_hdr.checksum = ~((~fwdl_checksum8((uint8_t *)&phy_hdr, sizeof(HIF_PHY_HDR))) +
                            (~fwdl_checksum8((uint8_t *)&msg_hdr, sizeof(HIF_MSG_HDR))));

    hif_memcpy(&hif_msg_heap[size], (void *)&phy_hdr, sizeof(HIF_PHY_HDR));
    size += sizeof(HIF_PHY_HDR);

    hif_memcpy(&hif_msg_heap[size], (void *)&msg_hdr, sizeof(HIF_MSG_HDR));
    size += sizeof(HIF_MSG_HDR);

#if (CONFIG_HIF_PROTO_VERSION == 0x02)
    hif_memcpy(&hif_msg_heap[size], (void *)payload, (length + 3)&(~0x3));
    size += (length + 3)&(~0x3);
#else
    hif_memcpy(&hif_msg_heap[size], (void *)payload, length);
    size += length;
#endif

    checksum32 = ~((~fwdl_checksum32((uint32_t *)&msg_hdr, sizeof(HIF_MSG_HDR))) +
                    (~fwdl_checksum32((uint32_t *)payload, length)));
    hif_memcpy(&hif_msg_heap[size], (void *)&checksum32, sizeof(checksum32));
    size += sizeof(checksum32);
    hif_debug_verb("start transfer buf size %d\n", size);

    hif_verb_hexdump("hif send:", (uint8_t *)&hif_msg_heap[0], size);

    //transmit fwdl msg
    ret = g_fw_download.write(&hif_msg_heap[0], size, 0);
    if (ret < 0) {
        hif_debug_log("fwdl transfer send  %d fail\n", length);
        goto exit;
    }

    //received ack msg
    ret = fwdl_receive_ack_msg(CONFIG_FWDL_ACK_TIMEOUT);
    if (ret < 0) {
        hif_debug_log("fwdl transfer receive ack fail\n");
    }

exit:
    hif_debug_verb("fwdl transfer end ret = %d\n", ret);
    return ret;
}
#endif

static int fwdl_send_reset_msg(uint8_t retry)
{
	int ret = 0;
	struct fwdl_reset_cmd_t reset_cmd = {
		.reset_cmd = FW_DOWNLOAD_CHIP_RESET_SUB_CMD,
	};
	do {
		ret = fwdl_send_hif_msg(FW_DOWNLOAD_RESET_CMD, (uint8_t *)&reset_cmd, sizeof(reset_cmd));
		if (ret == 0) {
			break;
		}
	} while (retry--);
	return ret;
}

static int fwdl_send_upload_msg(uint8_t retry)
{
	int ret = 0;
	struct fwdl_reset_cmd_t reset_cmd = {
		.reset_cmd = FW_DOWNLOAD_SOFT_RESET_SUB_CMD,
		.pram      = FW_DOWNLOAD_CTRL_UPLOAD_FLAG,
	};
	do {
		ret = fwdl_send_hif_msg(FW_DOWNLOAD_RESET_CMD, (uint8_t *)&reset_cmd, sizeof(reset_cmd));
		if (ret == 0) {
			break;
		}
	} while (retry--);
	return ret;
}

int fw_download_init(void)
{
    return g_fw_download.init();
}

int fw_download_sync(uint8_t retry_cnt)
{
    int ret = -1;
    uint8_t sync_code = HIF_PHY_SYNC_MAGIC, sync_ack = 0;
    ret = g_fw_download.init();
    if (ret < 0) {
        goto exit;
    }
    do {
        ret = g_fw_download.write((uint8_t *)&sync_code, sizeof(sync_code), 0);
        if (ret == 0) {
            ret = g_fw_download.read((uint8_t *)&sync_ack, sizeof(sync_ack), CONFIG_FW_DOWNLOAD_SYNC_TO);
            if (ret == 0) {
                if (sync_ack == HIF_PHY_ACK_MAGIC) {
                    sync_code = HIF_PHY_WKP_MAGIC;
                    hif_delay_us(10000);
                    ret = g_fw_download.write((uint8_t *)&sync_code, sizeof(sync_code), 0);
                    if (ret == 0) {
                        ret = g_fw_download.read((uint8_t *)&sync_ack, sizeof(sync_ack), CONFIG_FW_DOWNLOAD_SYNC_TO);
                        if (ret == 0) {
                            if (sync_ack == HIF_PHY_ACK_MAGIC) {
                                hif_debug_log("sync ack received\n");
                                break;
                            }
                        }
                    }
                }
                ret = -1;
            }
        }
        if (retry_cnt) {
            hif_debug_log("sync nack and retry remain %d\n", retry_cnt);
            hif_delay_us(10000);
        }
    } while (retry_cnt--);
#if CONFIG_HOST_IIC_EN
	if (retry_cnt) {
		g_fw_download.read((uint8_t *)&sync_ack, sizeof(sync_ack), CONFIG_FW_DOWNLOAD_SYNC_TO);
	}
#endif
exit:
    hif_debug_log("sync %d ret %d\n", retry_cnt, ret);
    return ret;
}

void fw_download_register(FWDL_INIT_CB_T init_cb, FWDL_WR_CB_T write_cb, FWDL_RD_CB_T read_cb)
{
    g_fw_download.init = init_cb;
    g_fw_download.write = write_cb;
    g_fw_download.read = read_cb;
}

void fw_image_read_register(FWDL_IMAGE_READ_CB_T image_read_cb)
{
    g_fw_download.image_read = image_read_cb;
}

int fw_image_read(uint32_t offset, void *data, uint32_t len)
{
    return g_fw_download.image_read(offset, data, len);
}

uint32_t fw_image_size_read(void)
{
    image_info_t image_info;
    int ret = 0;

    ret = fw_image_read(0, (void *)&image_info, sizeof(image_info));

    if ((ret != 0) || (image_info.magic != IMAGE_HEADER_MAGIC)) {
        return 0;
    }

    return image_info.size;
}

uint32_t fw_tlv_size_read(void)
{
    uint32_t tlv_offset = fw_image_size_read();
    tlv_info_t tlv_info;
    int ret = 0;

    /* read tlv head */
    ret = fw_image_read(tlv_offset, (void *)&tlv_info, sizeof(tlv_info));
    if ((ret != 0) || (tlv_info.magic != TLV_HEADER_MAGIC)) {
        return 0;
    }
    return tlv_info.size + sizeof(tlv_info) + 4;
}

uint16_t fw_image_load_tlv(uint8_t *buff, uint16_t max_size)
{
    uint32_t tlv_offset = fw_image_size_read();
    tlv_info_t tlv_info;
    int ret = 0;

    /* read tlv head */
    ret = fw_image_read(tlv_offset, (void *)&tlv_info, sizeof(tlv_info));
    if ((ret != 0) || (tlv_info.magic != TLV_HEADER_MAGIC) || (tlv_info.size > max_size)) {
        return 0;
    }

    /* read load tlv info */
    ret = fw_image_read(tlv_offset + sizeof(tlv_info), (uint8_t *)buff, tlv_info.size);
    if (ret) {
        return 0;
    }

    return tlv_info.size;
}

int fw_download_reset(uint8_t retry)
{
    return fwdl_send_reset_msg(retry);
}

int fw_download_upload(uint8_t retry)
{
	return fwdl_send_upload_msg(retry);
}

