"""Fast difference perceptual hash (dHash) and Hamming distance calculation.

Pure Python implementation with optional Pillow / NumPy acceleration when available.
Operates on raw grayscale bytes, raw RGB tuples / byte arrays, or PIL Image objects.

dHash: Neal Krawetz, The Hacker Factor Blog, "Looks Like It" (2011) and
"Kind of Like That" (2013). Hamming distance: R. Hamming (1950).
See docs/attributions.md.
"""

from typing import Union, Sequence

try:
    from PIL import Image  # type: ignore
except ImportError:
    Image = None


def compute_dhash_from_grayscale_grid(grid_9x8: Sequence[Sequence[int]]) -> int:
    """Compute 64-bit integer dhash from a 9x8 grid of grayscale pixel values.

    Rows: 8, Columns: 9.
    For each row, compare adjacent pixels: (pixel[col] > pixel[col + 1]) -> bit 1, else 0.
    Produces 8 * 8 = 64 bits.
    """
    diff_hash = 0
    for row in grid_9x8:
        for c in range(8):
            diff_hash = (diff_hash << 1) | (1 if row[c] > row[c + 1] else 0)
    return diff_hash


def _resize_and_grayscale_pure_python(
    raw_data: Union[bytes, bytearray, Sequence[int], Sequence[Sequence[int]]],
    width: int,
    height: int,
    channels: int = 1,
) -> list[list[int]]:
    """Resize image data to 9x8 grayscale using nearest-neighbor/box averaging.

    Supports:
    - raw_data as flat bytes/bytearray/sequence: length must be width * height * channels
      (e.g., grayscale if channels=1, RGB if channels=3, RGBA if channels=4)
    - raw_data as 2D sequence (height rows, width cols)
    """
    target_w = 9
    target_h = 8

    # Extract source pixel grayscale values: list of list of float/int
    if isinstance(raw_data, (bytes, bytearray, list, tuple)):
        # Check if 2D list
        if raw_data and isinstance(raw_data[0], (list, tuple)):
            src_rows = []
            for r in range(height):
                row_pixels = []
                for c in range(width):
                    val = raw_data[r][c]
                    if isinstance(val, (tuple, list)):
                        # RGB or RGBA tuple
                        gray = int(0.299 * val[0] + 0.587 * val[1] + 0.114 * val[2])
                    else:
                        gray = int(val)
                    row_pixels.append(gray)
                src_rows.append(row_pixels)
        else:
            # Flat buffer
            src_rows = []
            stride = width * channels
            for r in range(height):
                row_pixels = []
                row_offset = r * stride
                for c in range(width):
                    px_offset = row_offset + c * channels
                    if channels == 1:
                        gray = raw_data[px_offset]
                    else:
                        r_val = raw_data[px_offset]
                        g_val = raw_data[px_offset + 1]
                        b_val = raw_data[px_offset + 2]
                        gray = int(0.299 * r_val + 0.587 * g_val + 0.114 * b_val)
                    row_pixels.append(gray)
                src_rows.append(row_pixels)

    # Downsample src_rows (height x width) -> target_h x target_w (8 x 9)
    # Fast nearest neighbor sampling
    grid: list[list[int]] = []
    for y in range(target_h):
        src_y = min(int((y + 0.5) * height / target_h), height - 1)
        grid_row = []
        for x in range(target_w):
            src_x = min(int((x + 0.5) * width / target_w), width - 1)
            grid_row.append(src_rows[src_y][src_x])
        grid.append(grid_row)

    return grid


def compute_dhash_from_bytes(
    raw_data: Union[bytes, bytearray],
    width: int,
    height: int,
    channels: int = 1,
) -> int:
    """Compute 64-bit dhash integer directly from raw image bytes.

    :param raw_data: Raw buffer containing pixel bytes.
    :param width: Image width in pixels.
    :param height: Image height in pixels.
    :param channels: 1 for grayscale, 3 for RGB, 4 for RGBA.
    :return: 64-bit unsigned integer perceptual hash.
    """
    if Image is not None:
        try:
            mode = "L" if channels == 1 else ("RGB" if channels == 3 else "RGBA")
            img = Image.frombytes(mode, (width, height), bytes(raw_data))
            return compute_dhash(img)
        except Exception:
            pass

    grid = _resize_and_grayscale_pure_python(raw_data, width, height, channels=channels)
    return compute_dhash_from_grayscale_grid(grid)


def compute_dhash(image_or_pixels: Union["Image.Image", bytes, bytearray, Sequence[Sequence[int]]], width: int = 0, height: int = 0) -> int:
    """Compute 64-bit difference hash (dHash).

    Accepts:
    - PIL.Image.Image instance (width/height inferred)
    - 9x8 2D grayscale grid (if already resized)
    - Raw grayscale bytes if width and height are supplied
    """
    if Image is not None and isinstance(image_or_pixels, Image.Image):
        # PIL optimization: resize directly to 9x8, convert to grayscale
        small = image_or_pixels.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
        pixels = list(small.getdata())
        diff_hash = 0
        for r in range(8):
            row_start = r * 9
            for c in range(8):
                diff_hash = (diff_hash << 1) | (1 if pixels[row_start + c] > pixels[row_start + c + 1] else 0)
        return diff_hash

    if isinstance(image_or_pixels, (list, tuple)):
        # Check if already 9x8 grid (8 rows of 9 cols)
        if len(image_or_pixels) == 8 and len(image_or_pixels[0]) == 9:
            return compute_dhash_from_grayscale_grid(image_or_pixels)
        if width > 0 and height > 0:
            grid = _resize_and_grayscale_pure_python(image_or_pixels, width, height, channels=1)
            return compute_dhash_from_grayscale_grid(grid)

    if isinstance(image_or_pixels, (bytes, bytearray)):
        if width > 0 and height > 0:
            return compute_dhash_from_bytes(image_or_pixels, width, height)
        if len(image_or_pixels) == 72:  # 9 * 8 bytes
            grid = [
                [image_or_pixels[r * 9 + c] for c in range(9)]
                for r in range(8)
            ]
            return compute_dhash_from_grayscale_grid(grid)

    raise ValueError(f"Unsupported image input type or missing dimensions: {type(image_or_pixels)}")


def hamming_distance(hash1: int, hash2: int) -> int:
    """Calculate the Hamming distance between two 64-bit integer hashes.

    Hamming distance is the number of bit positions in which the two values differ.
    """
    diff = hash1 ^ hash2
    # int.bit_count() is standard in Python 3.10+ and highly optimized C
    return diff.bit_count()


def is_visually_static(prev_hash: int, curr_hash: int, threshold: int = 4) -> bool:
    """Determine whether two frames are visually static based on perceptual dHash.

    :param prev_hash: 64-bit dhash of previous frame.
    :param curr_hash: 64-bit dhash of current frame.
    :param threshold: Maximum Hamming distance to consider visually identical/static (default 4).
    :return: True if Hamming distance <= threshold, else False.
    """
    return hamming_distance(prev_hash, curr_hash) <= threshold
