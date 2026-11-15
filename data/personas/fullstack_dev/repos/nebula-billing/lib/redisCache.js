import { createClient } from "redis";

const REDIS_URL = process.env.REDIS_URL;
const client = createClient({ url: REDIS_URL });

client.on("error", (err) => console.error("Redis Client Error", err));

export async function initRedis() {
  if (!client.isOpen) await client.connect();
}

export async function getCachedUser(id) {
  const key = `user:${id}`;
  const data = await client.get(key);
  return data ? JSON.parse(data) : null;
}

export async function setCachedUser(id, user, ttl = 3600) {
  const key = `user:${id}`;
  await client.set(key, JSON.stringify(user), {
    EX: ttl,
  });
}

export async function invalidateUser(id) {
  await client.del(`user:${id}`);
}
