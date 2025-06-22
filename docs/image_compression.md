# Image Compression in Open WebUI

Open WebUI offers an optional **Image Compression** setting. When enabled, images selected for upload are resized in the browser before being attached to a chat or note. The UI exposes two numeric fields labelled **Image Max Compression Size** where users specify a maximum width and height.

If either width or height is provided, the front-end applies the `compressImage` helper from `src/lib/utils/index.ts`:

```typescript
export const compressImage = async (imageUrl, maxWidth, maxHeight) => {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            let width = img.width;
            let height = img.height;

            // Maintain aspect ratio while resizing
            if (maxWidth && maxHeight) {
                if (width <= maxWidth && height <= maxHeight) {
                    resolve(imageUrl);
                    return;
                }

                if (width / height > maxWidth / maxHeight) {
                    height = Math.round((maxWidth * height) / width);
                    width = maxWidth;
                } else {
                    width = Math.round((maxHeight * width) / height);
                    height = maxHeight;
                }
            } else if (maxWidth) {
                if (width <= maxWidth) {
                    resolve(imageUrl);
                    return;
                }
                height = Math.round((maxWidth * height) / width);
                width = maxWidth;
            } else if (maxHeight) {
                if (height <= maxHeight) {
                    resolve(imageUrl);
                    return;
                }
                width = Math.round((maxHeight * width) / height);
                height = maxHeight;
            }

            canvas.width = width;
            canvas.height = height;
            const context = canvas.getContext('2d');
            context.drawImage(img, 0, 0, width, height);
            const compressedUrl = canvas.toDataURL();
            resolve(compressedUrl);
        };
        img.onerror = (error) => reject(error);
        img.src = imageUrl;
    });
};
```

This routine loads the image into an off‑screen canvas, resizes it while preserving its aspect ratio and returns a new Base64 URL. If the original dimensions are already within the specified limits, the original URL is returned unchanged.

The width and height values are stored in `settings.imageCompressionSize` and persisted via `saveSettings()` in `Settings/Interface.svelte`. No hardcoded limits are enforced; leaving the fields blank disables resizing. The server never receives the uncompressed image when this feature is active—compression happens entirely client side.

