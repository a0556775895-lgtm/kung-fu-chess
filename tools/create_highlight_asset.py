# tools/create_highlight_asset.py
import numpy as np
import cv2

size = 256
img = np.zeros((size, size, 4), dtype=np.uint8)
img[:, :, 0] = 60    # B
img[:, :, 1] = 220   # G
img[:, :, 2] = 255   # R  -> צהוב-זהוב ב-BGR
img[:, :, 3] = 90    # alpha - שקיפות חלקית (0-255)

cv2.imwrite("view/assest/highlight.png", img)
print("נוצר: view/assest/highlight.png")
