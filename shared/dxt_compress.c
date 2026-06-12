/*
 * dxt_compress.c - DirectXTex BC1/BC3 compression with Floyd-Steinberg dithering
 *                  + Lanczos3 mipmap downsampling
 *
 * Pure C port of Microsoft DirectXTex BC.cpp (MIT License).
 * Ported from the C# implementation in Paint.NET-Tex-Plugin.
 *
 * Exports:
 *   compress_bc1(rgba, width, height, output, use_dithering, use_perceptual)
 *   compress_bc3(rgba, width, height, output, use_dithering, use_perceptual)
 *   downsample_lanczos3(src, src_w, src_h, dst, dst_w, dst_h)
 *
 * Build:
 *   gcc -shared -O3 -o dxt_compress.dll dxt_compress.c
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#ifdef _WIN32
#define DLL_EXPORT __declspec(dllexport)
#else
#define DLL_EXPORT
#endif

#define NUM_PIXELS_PER_BLOCK 16

/* Perceptual weightings from DirectXTex BC.cpp */
static const float LUM_R = 0.2125f / 0.7154f;
static const float LUM_G = 1.0f;
static const float LUM_B = 0.0721f / 0.7154f;
static const float LUM_R_INV = 0.7154f / 0.2125f;
static const float LUM_B_INV = 0.7154f / 0.0721f;

static float clamp01(float v) {
    if (v < 0.0f) return 0.0f;
    if (v > 1.0f) return 1.0f;
    return v;
}

static uint16_t encode_565(float r, float g, float b) {
    return (uint16_t)(
        ((int)(clamp01(r) * 31.0f + 0.5f) << 11) |
        ((int)(clamp01(g) * 63.0f + 0.5f) << 5) |
        (int)(clamp01(b) * 31.0f + 0.5f));
}

static void decode_565(uint16_t w, float *r, float *g, float *b) {
    *r = ((w >> 11) & 31) / 31.0f;
    *g = ((w >> 5) & 63) / 63.0f;
    *b = (w & 31) / 31.0f;
}

static void propagate_error(float *err_r, float *err_g, float *err_b,
                            int i, float dr, float dg, float db) {
    /* Right: 7/16 */
    if ((i & 3) != 3 && i < 15) {
        err_r[i + 1] += dr * (7.0f / 16.0f);
        err_g[i + 1] += dg * (7.0f / 16.0f);
        err_b[i + 1] += db * (7.0f / 16.0f);
    }
    /* Below row */
    if (i < 12) {
        /* Below-left: 3/16 */
        if ((i & 3) != 0) {
            err_r[i + 3] += dr * (3.0f / 16.0f);
            err_g[i + 3] += dg * (3.0f / 16.0f);
            err_b[i + 3] += db * (3.0f / 16.0f);
        }
        /* Below: 5/16 */
        err_r[i + 4] += dr * (5.0f / 16.0f);
        err_g[i + 4] += dg * (5.0f / 16.0f);
        err_b[i + 4] += db * (5.0f / 16.0f);
        /* Below-right: 1/16 */
        if ((i & 3) != 3) {
            err_r[i + 5] += dr * (1.0f / 16.0f);
            err_g[i + 5] += dg * (1.0f / 16.0f);
            err_b[i + 5] += db * (1.0f / 16.0f);
        }
    }
}

/* --------------------------------------------------------------------------
 * OptimizeRGB - port of BC.cpp lines 83-321
 * -------------------------------------------------------------------------- */

static void optimize_rgb(const float *color_r, const float *color_g, const float *color_b,
                         float *xr, float *xg, float *xb,
                         float *yr, float *yg, float *yb,
                         uint32_t u_steps) {
    int i;
    float ab_r, ab_g, ab_b, f_ab, f_ab_inv;
    float dir_r, dir_g, dir_b;
    float mid_r, mid_g, mid_b;
    float f_dir[4];
    int i_dir_max;
    float f_dir_max, t;
    float f_steps, f_epsilon;
    const float *pC, *pD;
    float pC4[] = {1.0f, 2.0f/3.0f, 1.0f/3.0f, 0.0f};
    float pD4[] = {0.0f, 1.0f/3.0f, 2.0f/3.0f, 1.0f};
    float pC3[] = {1.0f, 0.5f, 0.0f};
    float pD3[] = {0.0f, 0.5f, 1.0f};

    /* Find bounding box */
    *xr = *xg = *xb = 1.0f;
    *yr = *yg = *yb = 0.0f;

    for (i = 0; i < NUM_PIXELS_PER_BLOCK; i++) {
        if (color_r[i] < *xr) *xr = color_r[i];
        if (color_g[i] < *xg) *xg = color_g[i];
        if (color_b[i] < *xb) *xb = color_b[i];
        if (color_r[i] > *yr) *yr = color_r[i];
        if (color_g[i] > *yg) *yg = color_g[i];
        if (color_b[i] > *yb) *yb = color_b[i];
    }

    ab_r = *yr - *xr;
    ab_g = *yg - *xg;
    ab_b = *yb - *xb;
    f_ab = ab_r * ab_r + ab_g * ab_g + ab_b * ab_b;

    if (f_ab < 1.175494e-38f) return;

    /* Try all four axis directions */
    f_ab_inv = 1.0f / f_ab;
    dir_r = ab_r * f_ab_inv;
    dir_g = ab_g * f_ab_inv;
    dir_b = ab_b * f_ab_inv;

    mid_r = (*xr + *yr) * 0.5f;
    mid_g = (*xg + *yg) * 0.5f;
    mid_b = (*xb + *yb) * 0.5f;

    f_dir[0] = f_dir[1] = f_dir[2] = f_dir[3] = 0.0f;
    for (i = 0; i < NUM_PIXELS_PER_BLOCK; i++) {
        float pt_r = (color_r[i] - mid_r) * dir_r;
        float pt_g = (color_g[i] - mid_g) * dir_g;
        float pt_b = (color_b[i] - mid_b) * dir_b;
        float f;
        f = pt_r + pt_g + pt_b; f_dir[0] += f * f;
        f = pt_r + pt_g - pt_b; f_dir[1] += f * f;
        f = pt_r - pt_g + pt_b; f_dir[2] += f * f;
        f = pt_r - pt_g - pt_b; f_dir[3] += f * f;
    }

    i_dir_max = 0;
    f_dir_max = f_dir[0];
    for (i = 1; i < 4; i++) {
        if (f_dir[i] > f_dir_max) { f_dir_max = f_dir[i]; i_dir_max = i; }
    }

    if ((i_dir_max & 2) != 0) { t = *xg; *xg = *yg; *yg = t; }
    if ((i_dir_max & 1) != 0) { t = *xb; *xb = *yb; *yb = t; }

    /* Two-color block shortcut */
    if (f_ab < 1.0f / 4096.0f) {
        *xr = clamp01(*xr); *xg = clamp01(*xg); *xb = clamp01(*xb);
        *yr = clamp01(*yr); *yg = clamp01(*yg); *yb = clamp01(*yb);
        return;
    }

    /* Newton's method (8 iterations) */
    f_steps = (float)(u_steps - 1);
    f_epsilon = (0.25f / 64.0f) * (0.25f / 64.0f);

    if (u_steps == 4) { pC = pC4; pD = pD4; }
    else { pC = pC3; pD = pD3; }

    { int iter; for (iter = 0; iter < 8; iter++) {
        float dx_r = *yr - *xr, dx_g = *yg - *xg, dx_b = *yb - *xb;
        float f_len = dx_r * dx_r + dx_g * dx_g + dx_b * dx_b;
        float f_scl;
        float s_r[4], s_g[4], s_b[4];
        float d2x = 0, d2y = 0;
        float dXr = 0, dXg = 0, dXb = 0;
        float dYr = 0, dYg = 0, dYb = 0;

        if (f_len < 1.0f / 4096.0f) break;

        f_scl = f_steps / f_len;
        dx_r *= f_scl; dx_g *= f_scl; dx_b *= f_scl;

        for (i = 0; i < (int)u_steps; i++) {
            s_r[i] = *xr * pC[i] + *yr * pD[i];
            s_g[i] = *xg * pC[i] + *yg * pD[i];
            s_b[i] = *xb * pC[i] + *yb * pD[i];
        }

        for (i = 0; i < NUM_PIXELS_PER_BLOCK; i++) {
            float f_dot = (color_r[i] - *xr) * dx_r +
                          (color_g[i] - *xg) * dx_g +
                          (color_b[i] - *xb) * dx_b;
            int istep;
            float diff_r, diff_g, diff_b, fC_val, fD_val;

            if (f_dot <= 0.0f) istep = 0;
            else if (f_dot >= f_steps) istep = (int)u_steps - 1;
            else istep = (int)(f_dot + 0.5f);

            diff_r = s_r[istep] - color_r[i];
            diff_g = s_g[istep] - color_g[i];
            diff_b = s_b[istep] - color_b[i];

            fC_val = pC[istep] * (1.0f / 8.0f);
            fD_val = pD[istep] * (1.0f / 8.0f);

            d2x += fC_val * pC[istep];
            dXr += fC_val * diff_r;
            dXg += fC_val * diff_g;
            dXb += fC_val * diff_b;

            d2y += fD_val * pD[istep];
            dYr += fD_val * diff_r;
            dYg += fD_val * diff_g;
            dYb += fD_val * diff_b;
        }

        if (d2x > 0.0f) {
            float f = -1.0f / d2x;
            *xr += dXr * f; *xg += dXg * f; *xb += dXb * f;
        }
        if (d2y > 0.0f) {
            float f = -1.0f / d2y;
            *yr += dYr * f; *yg += dYg * f; *yb += dYb * f;
        }

        if (dXr*dXr < f_epsilon && dXg*dXg < f_epsilon && dXb*dXb < f_epsilon &&
            dYr*dYr < f_epsilon && dYg*dYg < f_epsilon && dYb*dYb < f_epsilon)
            break;
    }}

    *xr = clamp01(*xr); *xg = clamp01(*xg); *xb = clamp01(*xb);
    *yr = clamp01(*yr); *yg = clamp01(*yg); *yb = clamp01(*yb);
}

/* --------------------------------------------------------------------------
 * D3DXEncodeBC1 - exact port from DirectXTex BC.cpp
 * -------------------------------------------------------------------------- */

static void encode_bc1_block(const float *p_color_r, const float *p_color_g,
                             const float *p_color_b, uint8_t *output,
                             int use_dithering, int use_perceptual) {
    int i;
    uint32_t u_steps = 4;
    float color_r[16], color_g[16], color_b[16];
    float error_r[16], error_g[16], error_b[16];
    float xr, xg, xb, yr, yg, yb;
    float cr, cg, cb, dr, dg, db;
    uint16_t wA, wB;
    float ar2, ag2, ab2, br2, bg2, bb2;
    int swap;
    float step_r[4], step_g[4], step_b[4];
    float dir_r, dir_g, dir_b;
    float f_steps, f_len_sq, f_scale;
    int pSteps[] = {0, 2, 3, 1};
    uint32_t dw;

    memset(error_r, 0, sizeof(error_r));
    memset(error_g, 0, sizeof(error_g));
    memset(error_b, 0, sizeof(error_b));

    /* Phase 1: Quantize to RGB565 with optional dithering */
    for (i = 0; i < NUM_PIXELS_PER_BLOCK; i++) {
        float clr_r = p_color_r[i];
        float clr_g = p_color_g[i];
        float clr_b = p_color_b[i];

        if (use_dithering) {
            clr_r += error_r[i];
            clr_g += error_g[i];
            clr_b += error_b[i];
        }

        color_r[i] = (float)((int)(clr_r * 31.0f + 0.5f)) * (1.0f / 31.0f);
        color_g[i] = (float)((int)(clr_g * 63.0f + 0.5f)) * (1.0f / 63.0f);
        color_b[i] = (float)((int)(clr_b * 31.0f + 0.5f)) * (1.0f / 31.0f);

        if (use_dithering) {
            float diff_r = clr_r - color_r[i];
            float diff_g = clr_g - color_g[i];
            float diff_b = clr_b - color_b[i];
            propagate_error(error_r, error_g, error_b, i, diff_r, diff_g, diff_b);
        }

        if (use_perceptual) {
            color_r[i] *= LUM_R;
            color_g[i] *= LUM_G;
            color_b[i] *= LUM_B;
        }
    }

    /* Phase 2: OptimizeRGB */
    optimize_rgb(color_r, color_g, color_b, &xr, &xg, &xb, &yr, &yg, &yb, u_steps);

    if (use_perceptual) {
        cr = xr * LUM_R_INV; cg = xg; cb = xb * LUM_B_INV;
        dr = yr * LUM_R_INV; dg = yg; db = yb * LUM_B_INV;
    } else {
        cr = xr; cg = xg; cb = xb;
        dr = yr; dg = yg; db = yb;
    }

    wA = encode_565(cr, cg, cb);
    wB = encode_565(dr, dg, db);

    /* Degenerate case */
    if (u_steps == 4 && wA == wB) {
        output[0] = (uint8_t)(wA & 0xFF);
        output[1] = (uint8_t)(wA >> 8);
        output[2] = (uint8_t)(wB & 0xFF);
        output[3] = (uint8_t)(wB >> 8);
        output[4] = output[5] = output[6] = output[7] = 0;
        return;
    }

    decode_565(wA, &cr, &cg, &cb);
    decode_565(wB, &dr, &dg, &db);

    if (use_perceptual) {
        ar2 = cr * LUM_R; ag2 = cg * LUM_G; ab2 = cb * LUM_B;
        br2 = dr * LUM_R; bg2 = dg * LUM_G; bb2 = db * LUM_B;
    } else {
        ar2 = cr; ag2 = cg; ab2 = cb;
        br2 = dr; bg2 = dg; bb2 = db;
    }

    swap = (wA < wB);
    if (swap) {
        output[0] = (uint8_t)(wB & 0xFF); output[1] = (uint8_t)(wB >> 8);
        output[2] = (uint8_t)(wA & 0xFF); output[3] = (uint8_t)(wA >> 8);
        step_r[0] = br2; step_g[0] = bg2; step_b[0] = bb2;
        step_r[1] = ar2; step_g[1] = ag2; step_b[1] = ab2;
    } else {
        output[0] = (uint8_t)(wA & 0xFF); output[1] = (uint8_t)(wA >> 8);
        output[2] = (uint8_t)(wB & 0xFF); output[3] = (uint8_t)(wB >> 8);
        step_r[0] = ar2; step_g[0] = ag2; step_b[0] = ab2;
        step_r[1] = br2; step_g[1] = bg2; step_b[1] = bb2;
    }

    step_r[2] = step_r[0] + (step_r[1] - step_r[0]) * (1.0f / 3.0f);
    step_g[2] = step_g[0] + (step_g[1] - step_g[0]) * (1.0f / 3.0f);
    step_b[2] = step_b[0] + (step_b[1] - step_b[0]) * (1.0f / 3.0f);
    step_r[3] = step_r[0] + (step_r[1] - step_r[0]) * (2.0f / 3.0f);
    step_g[3] = step_g[0] + (step_g[1] - step_g[0]) * (2.0f / 3.0f);
    step_b[3] = step_b[0] + (step_b[1] - step_b[0]) * (2.0f / 3.0f);

    dir_r = step_r[1] - step_r[0];
    dir_g = step_g[1] - step_g[0];
    dir_b = step_b[1] - step_b[0];

    f_steps = (float)(u_steps - 1);
    f_len_sq = dir_r * dir_r + dir_g * dir_g + dir_b * dir_b;
    f_scale = (f_len_sq > 0) ? (f_steps / f_len_sq) : 0.0f;
    dir_r *= f_scale; dir_g *= f_scale; dir_b *= f_scale;

    /* Phase 3: Encode color indices */
    if (use_dithering) {
        memset(error_r, 0, sizeof(error_r));
        memset(error_g, 0, sizeof(error_g));
        memset(error_b, 0, sizeof(error_b));
    }

    dw = 0;
    for (i = 0; i < NUM_PIXELS_PER_BLOCK; i++) {
        float clr_r, clr_g, clr_b, f_dot;
        int istep;

        if (use_perceptual) {
            clr_r = p_color_r[i] * LUM_R;
            clr_g = p_color_g[i] * LUM_G;
            clr_b = p_color_b[i] * LUM_B;
        } else {
            clr_r = p_color_r[i];
            clr_g = p_color_g[i];
            clr_b = p_color_b[i];
        }

        if (use_dithering) {
            clr_r += error_r[i];
            clr_g += error_g[i];
            clr_b += error_b[i];
        }

        f_dot = (clr_r - step_r[0]) * dir_r +
                (clr_g - step_g[0]) * dir_g +
                (clr_b - step_b[0]) * dir_b;

        if (f_dot <= 0.0f) istep = 0;
        else if (f_dot >= f_steps) istep = 1;
        else istep = pSteps[(int)(f_dot + 0.5f)];

        dw = ((uint32_t)istep << 30) | (dw >> 2);

        if (use_dithering) {
            float diff_r = clr_r - step_r[istep];
            float diff_g = clr_g - step_g[istep];
            float diff_b = clr_b - step_b[istep];
            propagate_error(error_r, error_g, error_b, i, diff_r, diff_g, diff_b);
        }
    }

    output[4] = (uint8_t)(dw & 0xFF);
    output[5] = (uint8_t)((dw >> 8) & 0xFF);
    output[6] = (uint8_t)((dw >> 16) & 0xFF);
    output[7] = (uint8_t)((dw >> 24) & 0xFF);
}

/* --------------------------------------------------------------------------
 * BC3 alpha encoding
 * -------------------------------------------------------------------------- */

static void encode_bc3_alpha_block(const uint8_t *alphas, uint8_t *output) {
    uint8_t min_a = 255, max_a = 0;
    uint8_t palette[8];
    uint64_t bits = 0;
    int i, j;

    for (i = 0; i < 16; i++) {
        if (alphas[i] < min_a) min_a = alphas[i];
        if (alphas[i] > max_a) max_a = alphas[i];
    }

    output[0] = max_a;
    output[1] = min_a;

    palette[0] = max_a;
    palette[1] = min_a;

    if (max_a > min_a) {
        for (i = 1; i < 7; i++)
            palette[i + 1] = (uint8_t)((max_a * (7 - i) + min_a * i + 3) / 7);
    } else {
        for (i = 1; i < 5; i++)
            palette[i + 1] = (uint8_t)((max_a * (5 - i) + min_a * i + 2) / 5);
        palette[6] = 0;
        palette[7] = 255;
    }

    for (i = 0; i < 16; i++) {
        int best_idx = 0;
        int best_diff = abs((int)alphas[i] - (int)palette[0]);
        for (j = 1; j < 8; j++) {
            int diff = abs((int)alphas[i] - (int)palette[j]);
            if (diff < best_diff) { best_diff = diff; best_idx = j; }
        }
        bits |= ((uint64_t)best_idx << (i * 3));
    }

    for (i = 0; i < 6; i++)
        output[2 + i] = (uint8_t)(bits >> (i * 8));
}

/* --------------------------------------------------------------------------
 * Public API
 * -------------------------------------------------------------------------- */

DLL_EXPORT void compress_bc1(const uint8_t *rgba, int width, int height,
                             uint8_t *output, int use_dithering, int use_perceptual) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            float cr[16] = {0}, cg[16] = {0}, cb[16] = {0};
            int x, y;

            for (y = 0; y < 4; y++) {
                for (x = 0; x < 4; x++) {
                    int px = bx * 4 + x;
                    int py = by * 4 + y;
                    int idx = y * 4 + x;
                    if (px < width && py < height) {
                        int pi = (py * width + px) * 4;
                        cr[idx] = rgba[pi] / 255.0f;
                        cg[idx] = rgba[pi + 1] / 255.0f;
                        cb[idx] = rgba[pi + 2] / 255.0f;
                    }
                }
            }

            encode_bc1_block(cr, cg, cb, output + (by * block_w + bx) * 8,
                             use_dithering, use_perceptual);
        }
    }
}

DLL_EXPORT void compress_bc3(const uint8_t *rgba, int width, int height,
                             uint8_t *output, int use_dithering, int use_perceptual) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            float cr[16] = {0}, cg[16] = {0}, cb[16] = {0};
            uint8_t alpha[16];
            int x, y;
            int offset = (by * block_w + bx) * 16;

            memset(alpha, 255, sizeof(alpha));

            for (y = 0; y < 4; y++) {
                for (x = 0; x < 4; x++) {
                    int px = bx * 4 + x;
                    int py = by * 4 + y;
                    int idx = y * 4 + x;
                    if (px < width && py < height) {
                        int pi = (py * width + px) * 4;
                        cr[idx] = rgba[pi] / 255.0f;
                        cg[idx] = rgba[pi + 1] / 255.0f;
                        cb[idx] = rgba[pi + 2] / 255.0f;
                        alpha[idx] = rgba[pi + 3];
                    }
                }
            }

            encode_bc3_alpha_block(alpha, output + offset);
            encode_bc1_block(cr, cg, cb, output + offset + 8,
                             use_dithering, use_perceptual);
        }
    }
}

/* --------------------------------------------------------------------------
 * BC5 compression (two BC4 blocks: red, green)
 *
 * BC5 stores two independent 8-bit channels (R and G) as two BC4 blocks, the
 * same interpolated-endpoint format used by the DXT5 alpha block — so we reuse
 * encode_bc3_alpha_block() for each channel. Used for tangent-space normal maps
 * (X in red, Y in green). 16 bytes/block, no color/alpha. Decode reconstructs
 * the blue channel as the normal Z = sqrt(1 - x^2 - y^2) so it previews sanely.
 * -------------------------------------------------------------------------- */

DLL_EXPORT void compress_bc5(const uint8_t *rgba, int width, int height,
                             uint8_t *output) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            uint8_t red[16], green[16];
            int x, y;
            int offset = (by * block_w + bx) * 16;

            for (y = 0; y < 4; y++) {
                for (x = 0; x < 4; x++) {
                    int px = bx * 4 + x;
                    int py = by * 4 + y;
                    int idx = y * 4 + x;
                    /* clamp to edge for partial blocks */
                    int sx = px < width ? px : width - 1;
                    int sy = py < height ? py : height - 1;
                    int pi = (sy * width + sx) * 4;
                    red[idx]   = rgba[pi];
                    green[idx] = rgba[pi + 1];
                }
            }

            encode_bc3_alpha_block(red,   output + offset);
            encode_bc3_alpha_block(green, output + offset + 8);
        }
    }
}

/* Decode a single 8-byte BC4 block into 16 channel values. */
static void decode_bc4_block(const uint8_t *block, uint8_t out[16]) {
    uint8_t e0 = block[0], e1 = block[1];
    uint8_t vals[8];
    uint64_t bits = 0;
    int i;

    vals[0] = e0;
    vals[1] = e1;
    if (e0 > e1) {
        for (i = 1; i < 7; i++)
            vals[i + 1] = (uint8_t)(((7 - i) * e0 + i * e1) / 7);
    } else {
        for (i = 1; i < 5; i++)
            vals[i + 1] = (uint8_t)(((5 - i) * e0 + i * e1) / 5);
        vals[6] = 0;
        vals[7] = 255;
    }

    for (i = 0; i < 6; i++)
        bits |= ((uint64_t)block[2 + i]) << (i * 8);

    for (i = 0; i < 16; i++)
        out[i] = vals[(bits >> (i * 3)) & 0x7];
}

DLL_EXPORT void decompress_bc5(const uint8_t *input, int width, int height, uint8_t *rgba) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by, px, py;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            int off = (by * block_w + bx) * 16;
            uint8_t red[16], green[16];

            decode_bc4_block(input + off, red);
            decode_bc4_block(input + off + 8, green);

            for (py = 0; py < 4; py++) {
                for (px = 0; px < 4; px++) {
                    int x = bx * 4 + px, y = by * 4 + py;
                    int idx = py * 4 + px;
                    if (x < width && y < height) {
                        int pi = (y * width + x) * 4;
                        /* reconstruct normal-map Z from X=red, Y=green */
                        float nx = red[idx]   / 255.0f * 2.0f - 1.0f;
                        float ny = green[idx] / 255.0f * 2.0f - 1.0f;
                        float nz2 = 1.0f - nx * nx - ny * ny;
                        float nz = nz2 > 0.0f ? (float)sqrt(nz2) : 0.0f;
                        int b = (int)((nz * 0.5f + 0.5f) * 255.0f + 0.5f);
                        if (b < 0) b = 0; else if (b > 255) b = 255;
                        rgba[pi]   = red[idx];
                        rgba[pi+1] = green[idx];
                        rgba[pi+2] = (uint8_t)b;
                        rgba[pi+3] = 255;
                    }
                }
            }
        }
    }
}

/* --------------------------------------------------------------------------
 * DXT1/BC1 decompression
 * -------------------------------------------------------------------------- */

DLL_EXPORT void decompress_bc1(const uint8_t *input, int width, int height, uint8_t *rgba) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by, px, py;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            int off = (by * block_w + bx) * 8;
            uint16_t c0, c1;
            uint32_t bits;
            uint8_t r0, g0, b0, r1, g1, b1;
            uint8_t colors[4][4];

            c0 = input[off] | (input[off + 1] << 8);
            c1 = input[off + 2] | (input[off + 3] << 8);
            bits = input[off + 4] | (input[off + 5] << 8) |
                   (input[off + 6] << 16) | (input[off + 7] << 24);

            r0 = ((c0 >> 11) & 0x1F); r0 = (r0 << 3) | (r0 >> 2);
            g0 = ((c0 >> 5) & 0x3F);  g0 = (g0 << 2) | (g0 >> 4);
            b0 = (c0 & 0x1F);         b0 = (b0 << 3) | (b0 >> 2);
            r1 = ((c1 >> 11) & 0x1F); r1 = (r1 << 3) | (r1 >> 2);
            g1 = ((c1 >> 5) & 0x3F);  g1 = (g1 << 2) | (g1 >> 4);
            b1 = (c1 & 0x1F);         b1 = (b1 << 3) | (b1 >> 2);

            colors[0][0] = r0; colors[0][1] = g0; colors[0][2] = b0; colors[0][3] = 255;
            colors[1][0] = r1; colors[1][1] = g1; colors[1][2] = b1; colors[1][3] = 255;
            if (c0 > c1) {
                colors[2][0] = (2*r0+r1)/3; colors[2][1] = (2*g0+g1)/3; colors[2][2] = (2*b0+b1)/3; colors[2][3] = 255;
                colors[3][0] = (r0+2*r1)/3; colors[3][1] = (g0+2*g1)/3; colors[3][2] = (b0+2*b1)/3; colors[3][3] = 255;
            } else {
                colors[2][0] = (r0+r1)/2; colors[2][1] = (g0+g1)/2; colors[2][2] = (b0+b1)/2; colors[2][3] = 255;
                colors[3][0] = 0; colors[3][1] = 0; colors[3][2] = 0; colors[3][3] = 0;
            }

            for (py = 0; py < 4; py++) {
                for (px = 0; px < 4; px++) {
                    int x = bx * 4 + px, y = by * 4 + py;
                    if (x < width && y < height) {
                        int idx = (bits >> ((py * 4 + px) * 2)) & 3;
                        int pi = (y * width + x) * 4;
                        rgba[pi]   = colors[idx][0];
                        rgba[pi+1] = colors[idx][1];
                        rgba[pi+2] = colors[idx][2];
                        rgba[pi+3] = colors[idx][3];
                    }
                }
            }
        }
    }
}

/* --------------------------------------------------------------------------
 * DXT5/BC3 decompression
 * -------------------------------------------------------------------------- */

DLL_EXPORT void decompress_bc3(const uint8_t *input, int width, int height, uint8_t *rgba) {
    int block_w = (width + 3) / 4;
    int block_h = (height + 3) / 4;
    int bx, by, px, py, i;

    for (by = 0; by < block_h; by++) {
        for (bx = 0; bx < block_w; bx++) {
            int off = (by * block_w + bx) * 16;
            uint8_t a0, a1, alphas[8];
            uint64_t abits;
            uint16_t c0, c1;
            uint32_t bits;
            uint8_t r0, g0, b0, r1, g1, b1;
            uint8_t colors[4][3];

            /* Alpha block */
            a0 = input[off]; a1 = input[off + 1];
            abits = 0;
            for (i = 0; i < 6; i++)
                abits |= ((uint64_t)input[off + 2 + i] << (i * 8));

            alphas[0] = a0; alphas[1] = a1;
            if (a0 > a1) {
                for (i = 1; i < 7; i++)
                    alphas[i+1] = (uint8_t)(((7-i)*a0 + i*a1) / 7);
            } else {
                for (i = 1; i < 5; i++)
                    alphas[i+1] = (uint8_t)(((5-i)*a0 + i*a1) / 5);
                alphas[6] = 0; alphas[7] = 255;
            }

            /* Color block */
            c0 = input[off+8] | (input[off+9] << 8);
            c1 = input[off+10] | (input[off+11] << 8);
            bits = input[off+12] | (input[off+13] << 8) |
                   (input[off+14] << 16) | (input[off+15] << 24);

            r0 = ((c0 >> 11) & 0x1F); r0 = (r0 << 3) | (r0 >> 2);
            g0 = ((c0 >> 5) & 0x3F);  g0 = (g0 << 2) | (g0 >> 4);
            b0 = (c0 & 0x1F);         b0 = (b0 << 3) | (b0 >> 2);
            r1 = ((c1 >> 11) & 0x1F); r1 = (r1 << 3) | (r1 >> 2);
            g1 = ((c1 >> 5) & 0x3F);  g1 = (g1 << 2) | (g1 >> 4);
            b1 = (c1 & 0x1F);         b1 = (b1 << 3) | (b1 >> 2);

            colors[0][0] = r0; colors[0][1] = g0; colors[0][2] = b0;
            colors[1][0] = r1; colors[1][1] = g1; colors[1][2] = b1;
            colors[2][0] = (2*r0+r1)/3; colors[2][1] = (2*g0+g1)/3; colors[2][2] = (2*b0+b1)/3;
            colors[3][0] = (r0+2*r1)/3; colors[3][1] = (g0+2*g1)/3; colors[3][2] = (b0+2*b1)/3;

            for (py = 0; py < 4; py++) {
                for (px = 0; px < 4; px++) {
                    int x = bx * 4 + px, y = by * 4 + py;
                    if (x < width && y < height) {
                        int pidx = py * 4 + px;
                        int ci = (bits >> (pidx * 2)) & 3;
                        int ai = (int)((abits >> (pidx * 3)) & 7);
                        int pi = (y * width + x) * 4;
                        rgba[pi]   = colors[ci][0];
                        rgba[pi+1] = colors[ci][1];
                        rgba[pi+2] = colors[ci][2];
                        rgba[pi+3] = alphas[ai];
                    }
                }
            }
        }
    }
}

/* --------------------------------------------------------------------------
 * BGRA8 to RGBA conversion
 * -------------------------------------------------------------------------- */

DLL_EXPORT void decompress_bgra8(const uint8_t *input, int width, int height, uint8_t *rgba) {
    int i, total = width * height;
    for (i = 0; i < total; i++) {
        int off = i * 4;
        rgba[off]   = input[off + 2]; /* R */
        rgba[off+1] = input[off + 1]; /* G */
        rgba[off+2] = input[off];     /* B */
        rgba[off+3] = input[off + 3]; /* A */
    }
}

/* --------------------------------------------------------------------------
 * RGBA <-> BGRA byte swap
 * -------------------------------------------------------------------------- */

DLL_EXPORT void rgba_to_bgra(const uint8_t *rgba, uint8_t *bgra, int num_pixels) {
    int i;
    for (i = 0; i < num_pixels; i++) {
        int off = i * 4;
        bgra[off]     = rgba[off + 2]; /* B */
        bgra[off + 1] = rgba[off + 1]; /* G */
        bgra[off + 2] = rgba[off];     /* R */
        bgra[off + 3] = rgba[off + 3]; /* A */
    }
}

/* --------------------------------------------------------------------------
 * Lanczos3 mipmap downsampling
 * -------------------------------------------------------------------------- */

static double lanczos_kernel(double x, double a) {
    if (x == 0.0) return 1.0;
    if (x < -a || x > a) return 0.0;
    double pix = M_PI * x;
    return (sin(pix) / pix) * (sin(pix / a) / (pix / a));
}

DLL_EXPORT void downsample_lanczos3(const uint8_t *src, int src_w, int src_h,
                                     uint8_t *dst, int dst_w, int dst_h) {
    const double a = 3.0;
    double scale_x = (double)src_w / dst_w;
    double scale_y = (double)src_h / dst_h;
    int x, y;

    for (y = 0; y < dst_h; y++) {
        double src_y = (y + 0.5) * scale_y - 0.5;
        int y0 = (int)floor(src_y - a);
        int y1 = (int)ceil(src_y + a);
        if (y0 < 0) y0 = 0;
        if (y1 > src_h - 1) y1 = src_h - 1;

        for (x = 0; x < dst_w; x++) {
            double src_x = (x + 0.5) * scale_x - 0.5;
            int x0 = (int)floor(src_x - a);
            int x1 = (int)ceil(src_x + a);
            if (x0 < 0) x0 = 0;
            if (x1 > src_w - 1) x1 = src_w - 1;

            double r = 0, g = 0, b = 0, al = 0;
            double weight_sum = 0;
            int sy, sx;

            for (sy = y0; sy <= y1; sy++) {
                double wy = lanczos_kernel(sy - src_y, a);
                for (sx = x0; sx <= x1; sx++) {
                    double wx = lanczos_kernel(sx - src_x, a);
                    double w = wx * wy;
                    int si = (sy * src_w + sx) * 4;
                    r += src[si] * w;
                    g += src[si + 1] * w;
                    b += src[si + 2] * w;
                    al += src[si + 3] * w;
                    weight_sum += w;
                }
            }

            int di = (y * dst_w + x) * 4;
            if (weight_sum > 0) {
                double inv = 1.0 / weight_sum;
                double rv = r * inv + 0.5;
                double gv = g * inv + 0.5;
                double bv = b * inv + 0.5;
                double av = al * inv + 0.5;
                dst[di]     = (uint8_t)(rv < 0 ? 0 : (rv > 255 ? 255 : rv));
                dst[di + 1] = (uint8_t)(gv < 0 ? 0 : (gv > 255 ? 255 : gv));
                dst[di + 2] = (uint8_t)(bv < 0 ? 0 : (bv > 255 ? 255 : bv));
                dst[di + 3] = (uint8_t)(av < 0 ? 0 : (av > 255 ? 255 : av));
            }
        }
    }
}

/* --------------------------------------------------------------------------
 * Alpha bleed / edge-extend (in place)
 *
 * Fills the RGB of fully-transparent pixels with the average color of nearest
 * opaque/already-filled neighbors, via a multi-pass flood. Without this,
 * transparent pixels keep their (often white) RGB, which BC block-averaging and
 * mipmap downsampling smear into cutout edges -> white fringe. Alpha is left
 * untouched. Call this on the RGBA buffer BEFORE compression / downsampling.
 * -------------------------------------------------------------------------- */
DLL_EXPORT void alpha_bleed(uint8_t *rgba, int width, int height) {
    int n = width * height;
    if (n <= 0) return;

    uint8_t *filled = (uint8_t *)malloc((size_t)n);
    if (!filled) return;

    int any_transparent = 0;
    int i;
    for (i = 0; i < n; i++) {
        if (rgba[i * 4 + 3] != 0) {
            filled[i] = 1;
        } else {
            filled[i] = 0;
            any_transparent = 1;
        }
    }
    if (!any_transparent) { free(filled); return; }

    static const int DX[8] = { -1, 1, 0, 0, -1, 1, -1, 1 };
    static const int DY[8] = { 0, 0, -1, 1, -1, -1, 1, 1 };

    int max_passes = (width > height ? width : height);
    int *newly = (int *)malloc(sizeof(int) * (size_t)n);
    if (!newly) { free(filled); return; }

    int pass;
    for (pass = 0; pass < max_passes; pass++) {
        int newly_count = 0;
        int x, y, k;
        for (y = 0; y < height; y++) {
            for (x = 0; x < width; x++) {
                int p = y * width + x;
                if (filled[p]) continue;
                int rs = 0, gs = 0, bs = 0, cnt = 0;
                for (k = 0; k < 8; k++) {
                    int nx = x + DX[k], ny = y + DY[k];
                    if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
                    int np = ny * width + nx;
                    if (filled[np]) {
                        int o = np * 4;
                        rs += rgba[o]; gs += rgba[o + 1]; bs += rgba[o + 2]; cnt++;
                    }
                }
                if (cnt) {
                    int o = p * 4;
                    rgba[o]     = (uint8_t)(rs / cnt);
                    rgba[o + 1] = (uint8_t)(gs / cnt);
                    rgba[o + 2] = (uint8_t)(bs / cnt);
                    newly[newly_count++] = p;
                }
            }
        }
        if (newly_count == 0) break;
        for (i = 0; i < newly_count; i++) filled[newly[i]] = 1;
    }

    free(newly);
    free(filled);
}
