const capitalize = (str: string) => {
  if (!str) return "";
  if (str.length <= 1) return str.toUpperCase();
  return str.toUpperCase()[0] + str.slice(1);
};

function formatDate(timestamp: number) {
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) {
    return "Agora";
  }
  if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60);
    return `há ${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
  }
  if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600);
    return `há ${hours} ${hours === 1 ? "hora" : "horas"}`;
  }
  const days = Math.floor(diffInSeconds / 86400);
  return `há ${days} ${days === 1 ? "dia" : "dias"}`;
}

export { capitalize, formatDate };
