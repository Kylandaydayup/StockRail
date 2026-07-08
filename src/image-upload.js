const MAX_IMAGE_SIZE = 2 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

export function readAvatarFile(file) {
  if (!file || file.size === 0) {
    return Promise.resolve("");
  }
  if (!ALLOWED_TYPES.has(file.type)) {
    return Promise.reject(new Error("头像只支持 PNG、JPG、WebP 图片"));
  }
  if (file.size > MAX_IMAGE_SIZE) {
    return Promise.reject(new Error("头像图片不能超过 2MB"));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(new Error("头像读取失败，请重新选择")));
    reader.readAsDataURL(file);
  });
}
