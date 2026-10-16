import { getCameras } from "@/services/api";
import { usePolling } from "./usePolling";
export const useCameras = () => usePolling(getCameras, 30000);
