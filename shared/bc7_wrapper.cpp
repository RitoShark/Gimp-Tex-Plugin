/*
 * bc7_wrapper.cpp - extern "C" bridge to the bc7enc / bc7decomp BC7 codec.
 *
 * BC7 encode via Rich Geldreich's bc7enc (bc7enc/, MIT or public domain),
 * decode via bc7decomp. Compiled into libdxtcompress alongside dxt_compress.c
 * so the Python layer can bind compress_bc7/decompress_bc7 like the other
 * codecs. On Windows an optional Bc7Native.dll provides a faster DirectXTex
 * GPU path; this CPU encoder is the cross-platform baseline and the fallback
 * whenever the GPU DLL is missing or the GPU is unavailable.
 */

#include "bc7enc/bc7enc.h"
#include "bc7enc/bc7decomp.h"
#include <stdint.h>

#ifdef _WIN32
#define DLL_EXPORT __declspec(dllexport)
#else
#define DLL_EXPORT
#endif

extern "C" {

/* Encode RGBA (R-first) to BC7. perceptual: YCbCr error weighting if non-zero.
 * uber_level: 0 (fast) .. BC7ENC_MAX_UBER_LEVEL (slow, higher quality). */
DLL_EXPORT void compress_bc7(const uint8_t *rgba, int width, int height,
                             uint8_t *output, int perceptual, int uber_level) {
    static int inited = 0;
    if (!inited) { bc7enc_compress_block_init(); inited = 1; }

    bc7enc_compress_block_params params;
    bc7enc_compress_block_params_init(&params);
    if (perceptual)
        bc7enc_compress_block_params_init_perceptual_weights(&params);
    else
        bc7enc_compress_block_params_init_linear_weights(&params);

    if (uber_level < 0) uber_level = 0;
    if (uber_level > BC7ENC_MAX_UBER_LEVEL) uber_level = BC7ENC_MAX_UBER_LEVEL;
    params.m_uber_level = (uint32_t)uber_level;

    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by, x, y;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            uint8_t block_pixels[16 * 4];
            for (y = 0; y < 4; y++) {
                for (x = 0; x < 4; x++) {
                    int px = bx * 4 + x;
                    int py = by * 4 + y;
                    /* clamp to edge for partial blocks */
                    int sx = px < width ? px : width - 1;
                    int sy = py < height ? py : height - 1;
                    const uint8_t *src = rgba + (sy * width + sx) * 4;
                    uint8_t *dst = block_pixels + (y * 4 + x) * 4;
                    dst[0] = src[0]; dst[1] = src[1]; dst[2] = src[2]; dst[3] = src[3];
                }
            }
            uint8_t *out = output + (by * block_w + bx) * 16;
            bc7enc_compress_block(out, block_pixels, &params);
        }
    }
}

/* Decode BC7 blocks to RGBA (R-first). */
DLL_EXPORT void decompress_bc7(const uint8_t *input, int width, int height, uint8_t *rgba) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by, px, py;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            const uint8_t *blk = input + (by * block_w + bx) * 16;
            bc7decomp::color_rgba pixels[16];
            bc7decomp::unpack_bc7(blk, pixels);
            for (py = 0; py < 4; py++) {
                for (px = 0; px < 4; px++) {
                    int x = bx * 4 + px, y = by * 4 + py;
                    if (x < width && y < height) {
                        const bc7decomp::color_rgba &c = pixels[py * 4 + px];
                        uint8_t *d = rgba + (y * width + x) * 4;
                        d[0] = c.m_comps[0];
                        d[1] = c.m_comps[1];
                        d[2] = c.m_comps[2];
                        d[3] = c.m_comps[3];
                    }
                }
            }
        }
    }
}

} /* extern "C" */
