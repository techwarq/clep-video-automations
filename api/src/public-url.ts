const PRIVATE_HOST_SUFFIXES = [".localhost", ".local", ".internal", ".lan", ".home.arpa", ".intranet", ".corp"];
const IPV4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
const URL_IN_TEXT = /[a-z][a-z0-9+.-]*:\/\/[^\s,'"()[\]]+/gi;
export const MAX_URL_LENGTH = 2000;

function isPrivateIpv4(host: string): boolean {
  const match = host.match(IPV4);
  if (!match) return false;
  const [a, b] = [Number(match[1]), Number(match[2])];
  return a === 0 || a === 10 || a === 127 || a >= 224
    || (a === 100 && b >= 64 && b <= 127)
    || (a === 169 && b === 254)
    || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && b === 168)
    || (a === 198 && (b === 18 || b === 19));
}

function isPublicHostname(host: string): boolean {
  if (!host || host.startsWith("[")) return false;
  if (IPV4.test(host)) return !isPrivateIpv4(host);
  if (!host.includes(".") || host === "localhost") return false;
  return !PRIVATE_HOST_SUFFIXES.some((suffix) => host.endsWith(suffix));
}

export function isPublicWebUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length > MAX_URL_LENGTH) return false;
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return false;
  }
  const isWeb = url.protocol === "http:" || url.protocol === "https:";
  return isWeb && !url.username && !url.password && isPublicHostname(url.hostname.toLowerCase().replace(/\.$/, ""));
}

export const urlsInText = (text: string) =>
  [...text.matchAll(URL_IN_TEXT)].map((match) => match[0].replace(/[.,;!]+$/, ""));
