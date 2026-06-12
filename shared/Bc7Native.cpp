/*
 * Bc7Native.cpp - optional Windows-only GPU BC7 encoder (DirectXTex / DirectCompute).
 *
 * Wraps DirectXTex's GPU BC7 compressor. This DLL is an *accelerator* only: it is
 * bundled solely in the Windows installer and Windows release zips. When present
 * and a Direct3D 11 compute device is available, the Python layer prefers it for
 * BC7 encoding (fast). When absent or no GPU is available, the plugin falls back
 * to the cross-platform bc7enc CPU encoder compiled into libdxtcompress.
 *
 * Exports (cdecl):
 *   int encode_bc7_gpu(uint8_t *out, const uint8_t *rgba,
 *                      uint32_t width, uint32_t height, uint32_t flags)
 *       -> 1 on success, 0 on failure (caller falls back to CPU).
 *   int gpu_available(void) -> 1 if a D3D11 compute device can be created.
 *
 * Based on the Paint.NET TEX plugin's Bc7Native.cpp and Microsoft DirectXTex
 * (MIT License).
 */

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <wrl/client.h>
#include <cstdint>
#include <cstring>

#include "DirectXTex.h"

using namespace DirectX;
using Microsoft::WRL::ComPtr;

/* Build a DirectXTex ScratchImage from a flat RGBA8 buffer. */
static HRESULT MakeSourceImage(const uint8_t *inRgba, uint32_t width, uint32_t height, ScratchImage &out)
{
    HRESULT hr = out.Initialize2D(DXGI_FORMAT_R8G8B8A8_UNORM, width, height, 1, 1);
    if (FAILED(hr)) return hr;
    const Image *img = out.GetImage(0, 0, 0);
    if (!img) return E_FAIL;
    const size_t inRowBytes = (size_t)width * 4;
    for (uint32_t y = 0; y < height; ++y)
        std::memcpy(img->pixels + y * img->rowPitch, inRgba + y * inRowBytes, inRowBytes);
    return S_OK;
}

/* Copy compressed BC7 blocks (16 bytes/block) out of a ScratchImage. */
static void CopyBlocksOut(const Image &img, uint8_t *outBlocks, uint32_t width, uint32_t height)
{
    const uint32_t bw = (width + 3) / 4;
    const uint32_t bh = (height + 3) / 4;
    const size_t outRowBytes = (size_t)bw * 16;
    for (uint32_t by = 0; by < bh; ++by)
        std::memcpy(outBlocks + by * outRowBytes, img.pixels + by * img.rowPitch, outRowBytes);
}

static HRESULT CreateComputeDevice(ID3D11Device **ppDevice)
{
    D3D_FEATURE_LEVEL levels[] = {
        D3D_FEATURE_LEVEL_11_1,
        D3D_FEATURE_LEVEL_11_0,
        D3D_FEATURE_LEVEL_10_1,
        D3D_FEATURE_LEVEL_10_0,
    };
    D3D_FEATURE_LEVEL achieved = D3D_FEATURE_LEVEL_10_0;
    HRESULT hr = D3D11CreateDevice(
        nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr,
        0, levels, _countof(levels), D3D11_SDK_VERSION,
        ppDevice, &achieved, nullptr);
    if (FAILED(hr)) {
        /* Fall back to the WARP software rasterizer if no hardware device. */
        hr = D3D11CreateDevice(
            nullptr, D3D_DRIVER_TYPE_WARP, nullptr,
            0, levels, _countof(levels), D3D11_SDK_VERSION,
            ppDevice, &achieved, nullptr);
    }
    return hr;
}

extern "C" {

__declspec(dllexport) int __cdecl encode_bc7_gpu(
    uint8_t *out, const uint8_t *rgba,
    uint32_t width, uint32_t height, uint32_t flags)
{
    ComPtr<ID3D11Device> device;
    if (FAILED(CreateComputeDevice(device.GetAddressOf()))) return 0;

    ScratchImage src;
    if (FAILED(MakeSourceImage(rgba, width, height, src))) return 0;

    ScratchImage dst;
    HRESULT hr = Compress(
        device.Get(),
        src.GetImage(0, 0, 0), 1, src.GetMetadata(),
        DXGI_FORMAT_BC7_UNORM,
        (TEX_COMPRESS_FLAGS)flags,
        1.0f,
        dst);
    if (FAILED(hr)) return 0;

    const Image *dstImg = dst.GetImage(0, 0, 0);
    if (!dstImg) return 0;
    CopyBlocksOut(*dstImg, out, width, height);
    return 1;
}

__declspec(dllexport) int __cdecl gpu_available(void)
{
    ComPtr<ID3D11Device> device;
    return SUCCEEDED(CreateComputeDevice(device.GetAddressOf())) ? 1 : 0;
}

} /* extern "C" */
