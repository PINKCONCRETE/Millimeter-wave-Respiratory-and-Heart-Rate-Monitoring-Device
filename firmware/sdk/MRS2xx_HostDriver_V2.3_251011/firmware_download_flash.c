/**
 *   @file  firmware_flash_download.c
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

#if (CONFIG_FW_DOWNLOAD_SRAM == 0)

#define IMAGE_BUF_SIZE        (1024)  /* data and size must be align to 32bit. */
#define FWDL_RETRY_CNT        3
static uint8_t g_fw_image_buf[IMAGE_BUF_SIZE];

static int fwdl_send_flash_erase4k_msg(uint32_t fw_total_size)
{
    uint32_t erase_4k   = 4096;
    uint32_t erase_size = fw_total_size + ((erase_4k - (fw_total_size % erase_4k)) % erase_4k); /* 4k align */
    struct fwdl_flash_erase_cmd_t erase_cmd = {
        .addr = 0,
        .erase_type = FW_FLASH_ERASE_TYPE_4K,
        .block_num  = 1,
    };

    hif_debug_log("erase flash %d Bytes fw_size %d \n", erase_size, fw_total_size);

    for (int i = 0; i < erase_size / erase_4k; i++) {
        if (fwdl_send_hif_msg(FW_FLASH_ERASE_CMD, (uint8_t *)&erase_cmd, sizeof(struct fwdl_flash_erase_cmd_t)) == 0) {
            erase_cmd.addr += erase_4k;
        } else {
            return -1;
        }
    }

    return 0;
}

uint8_t send_flash_msg_data[FWDL_FLASH_WRITE_SIZE + sizeof(struct fwdl_flash_write_cmd_t)];
static int fwdl_send_flash_msg(uint32_t addr, uint8_t *data, uint32_t fw_size)
{
    int ret = 0;
    uint32_t pos = 0;
    uint32_t cmd_offset = sizeof(struct fwdl_flash_write_cmd_t);
    struct fwdl_flash_write_cmd_t *write_cmd = (struct fwdl_flash_write_cmd_t *)&send_flash_msg_data[0];
    write_cmd->addr = addr;
    write_cmd->len  = 0;
    pos += cmd_offset;


    while (fw_size) {
        hif_debug_log("write addr 0x%08x  size %d \n", write_cmd->addr, fw_size);

        if (fw_size >= FWDL_FLASH_WRITE_SIZE) {
            memcpy(&send_flash_msg_data[pos], data, FWDL_FLASH_WRITE_SIZE);
            write_cmd->len = FWDL_FLASH_WRITE_SIZE;

            ret = fwdl_send_hif_msg(FW_FLASH_WRITE_CMD, (uint8_t *)&send_flash_msg_data[0], sizeof(struct fwdl_flash_write_cmd_t) + FWDL_FLASH_WRITE_SIZE);

            fw_size -= FWDL_FLASH_WRITE_SIZE;
            write_cmd->addr += FWDL_FLASH_WRITE_SIZE;
            pos += FWDL_FLASH_WRITE_SIZE;
        } else {
            memcpy(&send_flash_msg_data[pos], data, fw_size);
            write_cmd->len = fw_size;

            ret = fwdl_send_hif_msg(FW_FLASH_WRITE_CMD, (uint8_t *)&send_flash_msg_data[0], sizeof(struct fwdl_flash_write_cmd_t) + fw_size);

            fw_size = 0;
            pos = 0;
        }
    }
    return ret;
}

int fw_download_start_flash(uint32_t fw_total_size)
{
	int ret;

    ret = fw_download_init();
    if (ret < 0) {
        hif_debug_log("%s, interface driver init fail", __FUNCTION__);
        goto exit;
    }

    hif_debug_verb("goto to sync\n");
    ret = fw_download_sync(CONFIG_FW_DOWNLOAD_SYNC_RETRY);
    if (ret < 0) {
        hif_debug_log("%s, sync fail", __FUNCTION__);
        goto exit;
    }

    ret = fwdl_send_flash_erase4k_msg(fw_total_size);

exit:
    hif_debug_log("fw download start end, ret = %d\n", ret);
    return ret;
}

int fw_download_data_flash(uint32_t addr, uint8_t *data, uint16_t length)
{
    int ret;
    hif_debug_verb("goto download data size %d\n", length);
    ret = fwdl_send_flash_msg(addr, data, length);
    if (ret < 0) {
        hif_debug_log("fw download data fail ret %d", ret);
    }
    return ret;
}

int firmware_download_flash(void)
{
    int ret;
    uint32_t image_offset, read_size, image_size = fw_image_size_read() + fw_tlv_size_read();
    ret = fw_download_start_flash(image_size);
    if (ret) {
        hif_debug_log("download start err \n");
        return ret;
    }

    image_offset = 0;
    while (image_size) {
        if (image_size >= IMAGE_BUF_SIZE) {
            read_size = IMAGE_BUF_SIZE;
        } else {
            read_size = image_size;
        }
        ret = fw_image_read(image_offset, (uint8_t *)&g_fw_image_buf[0], read_size);
        if (ret) {
            hif_debug_log("read image fail offset %d read_size %d\n", image_offset, read_size);
            return ret;
        }
        ret = fw_download_data_flash(image_offset, (uint8_t *)&g_fw_image_buf[0], read_size);
        if (ret) {
            hif_debug_log("download fail offset %d read_size %d\n", image_offset, read_size);
            return ret;
        }
        image_size -= read_size;
        image_offset += read_size;
    }
    return 0;
}

int sensor_download(void)
{
    int ret;
    int retry = FWDL_RETRY_CNT;
    do {
        /*retry sync for 100 times*/
        ret = fw_download_sync(100);
        if (ret < 0) {
            hif_debug_log("firmware download sync fail\n");
        } else {
            /*reboot mmwave firmware to prepare firmware download, retry 3 times*/
            ret = fw_download_upload(retry);

            if (ret < 0) {
                hif_debug_log("firmware download reset fail\n");
            } else {
                ret = firmware_download_flash();
                if (ret == 0) {
                    fw_download_reset(retry);
#if CONFIG_HOST_IIC_EN
                    /* wait 750ms to reset */
                    hif_delay_us(750000);
#else
                    /* wait 50ms to reset */
                    hif_delay_us(50000);
#endif
                    break;
                }
            }
        }
    } while (retry--);

    hif_debug_log("%s ret %d\n", __FUNCTION__, ret);
    return ret;
}
#endif /* CONFIG_FW_DOWNLOAD_SRAM == 0 */

