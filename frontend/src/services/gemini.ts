import { getWittyResponse as apiWitty } from './api';

export async function getWittyResponse(objective: string) {
  try {
    const data = await apiWitty(objective);
    return data.content || data.response || "Drop your files. Let's sort this mess out.";
  } catch {
    return "Drop your files. Let's sort this mess out.";
  }
}
