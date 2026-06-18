import { useState, useCallback } from 'react';

export function usePasteImage(onImagePasted: (base64: string) => void) {
  const [pastedFile, setPastedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        e.preventDefault();
        const file = items[i].getAsFile();

        if (file) {
          const reader = new FileReader();
          reader.onload = (event) => {
            const base64String = event.target?.result as string;
            setPreviewUrl(base64String);
            setPastedFile(null); // Backend handles query as base64
            onImagePasted(base64String);
          };
          reader.readAsDataURL(file);
        }
        break;
      }
    }
  }, [onImagePasted]);

  const clearImage = useCallback(() => {
    setPreviewUrl(null);
    setPastedFile(null);
  }, []);

  return {
    pastedFile,
    previewUrl,
    handlePaste,
    clearImage
  };
}