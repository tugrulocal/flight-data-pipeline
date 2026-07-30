const numberFormatter = new Intl.NumberFormat("tr-TR", {
  maximumFractionDigits: 0,
});

const decimalFormatter = new Intl.NumberFormat("tr-TR", {
  maximumFractionDigits: 1,
});


export function formatAltitude(value: number | null) {
  return value === null ? "—" : `${numberFormatter.format(value)} m`;
}


export function formatSpeed(value: number | null) {
  if (value === null) {
    return "—";
  }

  return `${numberFormatter.format(value * 3.6)} km/sa`;
}


export function formatHeading(value: number | null) {
  return value === null ? "—" : `${numberFormatter.format(value)}°`;
}


export function formatCoordinate(value: number) {
  return decimalFormatter.format(value);
}


export function formatTime(value: string | null) {
  if (!value) {
    return "Bilinmiyor";
  }

  return new Intl.DateTimeFormat("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}


export function formatDateTime(value: string | null) {
  if (!value) {
    return "Bilinmiyor";
  }

  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}


export function formatRelativeTime(value: string | null) {
  if (!value) {
    return "zaman yok";
  }

  const seconds = Math.max(
    0,
    Math.round((Date.now() - new Date(value).getTime()) / 1000),
  );

  if (seconds < 60) {
    return `${seconds} sn önce`;
  }

  const minutes = Math.floor(seconds / 60);

  if (minutes < 60) {
    return `${minutes} dk önce`;
  }

  return `${Math.floor(minutes / 60)} sa önce`;
}
