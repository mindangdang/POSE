const API_IMAGE_PREFIX = '/api/images/';

function normalizeLocalImagePath(imageUrl: string) {
  return imageUrl
    .replace(/^\/+api\/images\//, '')
    .replace(/^\/+images\//, '')
    .replace(/^\/+/, '');
}

export function getDisplayImageUrl(
  imageUrl?: string | null,
  localImageUrl?: string | null,
  fallbackUrl = 'https://via.placeholder.com/400x400?text=No+Image',
) {
  const candidate = localImageUrl || imageUrl || '';

  if (!candidate) return fallbackUrl;
  if (candidate.startsWith('http://') || candidate.startsWith('https://') || candidate.startsWith('data:')) {
    return candidate;
  }
  if (candidate.startsWith('//')) {
    return `https:${candidate}`;
  }

  const normalizedPath = normalizeLocalImagePath(candidate);
  return normalizedPath ? `${API_IMAGE_PREFIX}${normalizedPath}` : fallbackUrl;
}

export function getFallbackImageUrl(text = 'No+Image') {
  return `https://via.placeholder.com/400x400?text=${text}`;
}