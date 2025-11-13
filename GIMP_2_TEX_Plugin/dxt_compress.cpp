/*
Fast DXT5 compression library for GIMP TEX plugin
Compile with: cl /LD /O2 dxt_compress.cpp /Fe:dxt_compress.dll
Or with MinGW: g++ -shared -O3 -o dxt_compress.dll dxt_compress.cpp
*/

#include <cstdint>
#include <algorithm>

extern "C" {

// Convert RGB888 to RGB565
inline uint16_t rgb_to_565(uint8_t r, uint8_t g, uint8_t b) {
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
}

// Compress a single 4x4 block to DXT5
void compress_dxt5_block(const uint8_t* rgba, int x, int y, int width, int height, uint8_t* output) {
    uint8_t block_rgba[16][4];
    uint8_t alphas[16];
    
    // Extract 4x4 block
    for (int py = 0; py < 4; py++) {
        for (int px = 0; px < 4; px++) {
            int idx = py * 4 + px;
            int img_x = x + px;
            int img_y = y + py;
            
            if (img_x < width && img_y < height) {
                int pixel_idx = (img_y * width + img_x) * 4;
                block_rgba[idx][0] = rgba[pixel_idx];
                block_rgba[idx][1] = rgba[pixel_idx + 1];
                block_rgba[idx][2] = rgba[pixel_idx + 2];
                block_rgba[idx][3] = rgba[pixel_idx + 3];
                alphas[idx] = rgba[pixel_idx + 3];
            } else {
                block_rgba[idx][0] = 0;
                block_rgba[idx][1] = 0;
                block_rgba[idx][2] = 0;
                block_rgba[idx][3] = 0;
                alphas[idx] = 0;
            }
        }
    }
    
    // Compress alpha
    uint8_t alpha0 = alphas[0];
    uint8_t alpha1 = alphas[0];
    for (int i = 1; i < 16; i++) {
        alpha0 = std::min(alpha0, alphas[i]);
        alpha1 = std::max(alpha1, alphas[i]);
    }
    
    output[0] = alpha0;
    output[1] = alpha1;
    
    // Calculate alpha palette
    uint8_t alpha_palette[8];
    alpha_palette[0] = alpha0;
    alpha_palette[1] = alpha1;
    if (alpha0 > alpha1) {
        for (int i = 1; i < 7; i++) {
            alpha_palette[i + 1] = ((7 - i) * alpha0 + i * alpha1) / 7;
        }
    } else {
        for (int i = 1; i < 5; i++) {
            alpha_palette[i + 1] = ((5 - i) * alpha0 + i * alpha1) / 5;
        }
        alpha_palette[6] = 0;
        alpha_palette[7] = 255;
    }
    
    // Encode alpha indices
    uint64_t alpha_bits = 0;
    for (int i = 0; i < 16; i++) {
        uint8_t alpha = alphas[i];
        int best_idx = 0;
        int best_diff = abs(alpha - alpha_palette[0]);
        for (int j = 1; j < 8; j++) {
            int diff = abs(alpha - alpha_palette[j]);
            if (diff < best_diff) {
                best_diff = diff;
                best_idx = j;
            }
        }
        alpha_bits |= ((uint64_t)best_idx << (i * 3));
    }
    
    for (int i = 0; i < 6; i++) {
        output[2 + i] = (alpha_bits >> (i * 8)) & 0xFF;
    }
    
    // Compress color - find min/max by luminance
    int min_lum = 999999;
    int max_lum = 0;
    uint8_t color0_rgb[3] = {0, 0, 0};
    uint8_t color1_rgb[3] = {0, 0, 0};
    
    for (int i = 0; i < 16; i++) {
        int lum = block_rgba[i][0] * 2 + block_rgba[i][1] * 4 + block_rgba[i][2];
        if (lum < min_lum) {
            min_lum = lum;
            color0_rgb[0] = block_rgba[i][0];
            color0_rgb[1] = block_rgba[i][1];
            color0_rgb[2] = block_rgba[i][2];
        }
        if (lum > max_lum) {
            max_lum = lum;
            color1_rgb[0] = block_rgba[i][0];
            color1_rgb[1] = block_rgba[i][1];
            color1_rgb[2] = block_rgba[i][2];
        }
    }
    
    uint16_t color0 = rgb_to_565(color0_rgb[0], color0_rgb[1], color0_rgb[2]);
    uint16_t color1 = rgb_to_565(color1_rgb[0], color1_rgb[1], color1_rgb[2]);
    
    // Reconstruct colors from 565
    uint8_t r0 = ((color0 >> 11) & 0x1F) << 3;
    uint8_t g0 = ((color0 >> 5) & 0x3F) << 2;
    uint8_t b0 = (color0 & 0x1F) << 3;
    uint8_t r1 = ((color1 >> 11) & 0x1F) << 3;
    uint8_t g1 = ((color1 >> 5) & 0x3F) << 2;
    uint8_t b1 = (color1 & 0x1F) << 3;
    
    // Color palette
    uint8_t color_palette[4][3] = {
        {r0, g0, b0},
        {r1, g1, b1},
        {(uint8_t)((r0 * 2 + r1) / 3), (uint8_t)((g0 * 2 + g1) / 3), (uint8_t)((b0 * 2 + b1) / 3)},
        {(uint8_t)((r0 + r1 * 2) / 3), (uint8_t)((g0 + g1 * 2) / 3), (uint8_t)((b0 + b1 * 2) / 3)}
    };
    
    // Encode color indices
    uint32_t color_bits = 0;
    for (int i = 0; i < 16; i++) {
        int best_idx = 0;
        int best_diff = 999999;
        for (int j = 0; j < 4; j++) {
            int dr = block_rgba[i][0] - color_palette[j][0];
            int dg = block_rgba[i][1] - color_palette[j][1];
            int db = block_rgba[i][2] - color_palette[j][2];
            int diff = dr * dr + dg * dg + db * db;
            if (diff < best_diff) {
                best_diff = diff;
                best_idx = j;
            }
        }
        color_bits |= (best_idx << (i * 2));
    }
    
    output[8] = color0 & 0xFF;
    output[9] = (color0 >> 8) & 0xFF;
    output[10] = color1 & 0xFF;
    output[11] = (color1 >> 8) & 0xFF;
    output[12] = color_bits & 0xFF;
    output[13] = (color_bits >> 8) & 0xFF;
    output[14] = (color_bits >> 16) & 0xFF;
    output[15] = (color_bits >> 24) & 0xFF;
}

// Main compression function
__declspec(dllexport) void compress_dxt5(const uint8_t* rgba, int width, int height, uint8_t* output) {
    int block_width = (width + 3) / 4;
    int block_height = (height + 3) / 4;
    
    for (int by = 0; by < block_height; by++) {
        for (int bx = 0; bx < block_width; bx++) {
            int block_idx = (by * block_width + bx) * 16;
            compress_dxt5_block(rgba, bx * 4, by * 4, width, height, output + block_idx);
        }
    }
}

// Fast DXT1 decompression
void decompress_dxt1_block(const uint8_t* input, int x, int y, int width, int height, uint8_t* rgba) {
    // Read color values
    uint16_t color0 = input[0] | (input[1] << 8);
    uint16_t color1 = input[2] | (input[3] << 8);
    uint32_t color_bits = input[4] | (input[5] << 8) | (input[6] << 16) | (input[7] << 24);
    
    // Convert 565 to RGB888
    uint8_t r0 = ((color0 >> 11) & 0x1F) << 3;
    uint8_t g0 = ((color0 >> 5) & 0x3F) << 2;
    uint8_t b0 = (color0 & 0x1F) << 3;
    uint8_t r1 = ((color1 >> 11) & 0x1F) << 3;
    uint8_t g1 = ((color1 >> 5) & 0x3F) << 2;
    uint8_t b1 = (color1 & 0x1F) << 3;
    
    // Build color palette
    uint8_t color_palette[4][4];  // RGBA
    color_palette[0][0] = r0; color_palette[0][1] = g0; color_palette[0][2] = b0; color_palette[0][3] = 255;
    color_palette[1][0] = r1; color_palette[1][1] = g1; color_palette[1][2] = b1; color_palette[1][3] = 255;
    
    if (color0 > color1) {
        color_palette[2][0] = (r0 * 2 + r1) / 3;
        color_palette[2][1] = (g0 * 2 + g1) / 3;
        color_palette[2][2] = (b0 * 2 + b1) / 3;
        color_palette[2][3] = 255;
        color_palette[3][0] = (r0 + r1 * 2) / 3;
        color_palette[3][1] = (g0 + g1 * 2) / 3;
        color_palette[3][2] = (b0 + b1 * 2) / 3;
        color_palette[3][3] = 255;
    } else {
        color_palette[2][0] = (r0 + r1) / 2;
        color_palette[2][1] = (g0 + g1) / 2;
        color_palette[2][2] = (b0 + b1) / 2;
        color_palette[2][3] = 255;
        color_palette[3][0] = 0;
        color_palette[3][1] = 0;
        color_palette[3][2] = 0;
        color_palette[3][3] = 0;  // Transparent
    }
    
    // Decode pixels
    for (int py = 0; py < 4; py++) {
        for (int px = 0; px < 4; px++) {
            int img_x = x + px;
            int img_y = y + py;
            
            if (img_x < width && img_y < height) {
                int idx = py * 4 + px;
                int pixel_idx = (img_y * width + img_x) * 4;
                
                // Get color index
                int color_idx = (color_bits >> (idx * 2)) & 3;
                rgba[pixel_idx] = color_palette[color_idx][0];
                rgba[pixel_idx + 1] = color_palette[color_idx][1];
                rgba[pixel_idx + 2] = color_palette[color_idx][2];
                rgba[pixel_idx + 3] = color_palette[color_idx][3];
            }
        }
    }
}

// Fast DXT5 decompression
void decompress_dxt5_block(const uint8_t* input, int x, int y, int width, int height, uint8_t* rgba) {
    // Read alpha values
    uint8_t alpha0 = input[0];
    uint8_t alpha1 = input[1];
    
    // Read alpha bits
    uint64_t alpha_bits = 0;
    for (int i = 0; i < 6; i++) {
        alpha_bits |= ((uint64_t)input[2 + i] << (i * 8));
    }
    
    // Build alpha palette
    uint8_t alpha_palette[8];
    alpha_palette[0] = alpha0;
    alpha_palette[1] = alpha1;
    if (alpha0 > alpha1) {
        for (int i = 1; i < 7; i++) {
            alpha_palette[i + 1] = ((7 - i) * alpha0 + i * alpha1) / 7;
        }
    } else {
        for (int i = 1; i < 5; i++) {
            alpha_palette[i + 1] = ((5 - i) * alpha0 + i * alpha1) / 5;
        }
        alpha_palette[6] = 0;
        alpha_palette[7] = 255;
    }
    
    // Read color values
    uint16_t color0 = input[8] | (input[9] << 8);
    uint16_t color1 = input[10] | (input[11] << 8);
    uint32_t color_bits = input[12] | (input[13] << 8) | (input[14] << 16) | (input[15] << 24);
    
    // Convert 565 to RGB888
    uint8_t r0 = ((color0 >> 11) & 0x1F) << 3;
    uint8_t g0 = ((color0 >> 5) & 0x3F) << 2;
    uint8_t b0 = (color0 & 0x1F) << 3;
    uint8_t r1 = ((color1 >> 11) & 0x1F) << 3;
    uint8_t g1 = ((color1 >> 5) & 0x3F) << 2;
    uint8_t b1 = (color1 & 0x1F) << 3;
    
    // Build color palette
    uint8_t color_palette[4][3] = {
        {r0, g0, b0},
        {r1, g1, b1},
        {(uint8_t)((r0 * 2 + r1) / 3), (uint8_t)((g0 * 2 + g1) / 3), (uint8_t)((b0 * 2 + b1) / 3)},
        {(uint8_t)((r0 + r1 * 2) / 3), (uint8_t)((g0 + g1 * 2) / 3), (uint8_t)((b0 + b1 * 2) / 3)}
    };
    
    // Decode pixels
    for (int py = 0; py < 4; py++) {
        for (int px = 0; px < 4; px++) {
            int img_x = x + px;
            int img_y = y + py;
            
            if (img_x < width && img_y < height) {
                int idx = py * 4 + px;
                int pixel_idx = (img_y * width + img_x) * 4;
                
                // Get color index
                int color_idx = (color_bits >> (idx * 2)) & 3;
                rgba[pixel_idx] = color_palette[color_idx][0];
                rgba[pixel_idx + 1] = color_palette[color_idx][1];
                rgba[pixel_idx + 2] = color_palette[color_idx][2];
                
                // Get alpha index
                int alpha_idx = (alpha_bits >> (idx * 3)) & 7;
                rgba[pixel_idx + 3] = alpha_palette[alpha_idx];
            }
        }
    }
}

// Main DXT1 decompression function
__declspec(dllexport) void decompress_dxt1(const uint8_t* input, int width, int height, uint8_t* rgba) {
    int block_width = (width + 3) / 4;
    int block_height = (height + 3) / 4;
    
    // Initialize output to black/transparent
    int pixel_count = width * height * 4;
    for (int i = 0; i < pixel_count; i++) {
        rgba[i] = 0;
    }
    
    for (int by = 0; by < block_height; by++) {
        for (int bx = 0; bx < block_width; bx++) {
            int block_idx = (by * block_width + bx) * 8;  // DXT1 is 8 bytes per block
            decompress_dxt1_block(input + block_idx, bx * 4, by * 4, width, height, rgba);
        }
    }
}

// Main DXT5 decompression function
__declspec(dllexport) void decompress_dxt5(const uint8_t* input, int width, int height, uint8_t* rgba) {
    int block_width = (width + 3) / 4;
    int block_height = (height + 3) / 4;
    
    // Initialize output to black/transparent
    int pixel_count = width * height * 4;
    for (int i = 0; i < pixel_count; i++) {
        rgba[i] = 0;
    }
    
    for (int by = 0; by < block_height; by++) {
        for (int bx = 0; bx < block_width; bx++) {
            int block_idx = (by * block_width + bx) * 16;  // DXT5 is 16 bytes per block
            decompress_dxt5_block(input + block_idx, bx * 4, by * 4, width, height, rgba);
        }
    }
}

} // extern "C"
