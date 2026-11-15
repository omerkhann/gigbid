import { createClient, RedisClientType } from 'redis'

let client: RedisClientType | null = null

export function getClient(): RedisClientType {
  if (!client) {
    client = createClient({ url: process.env.REDIS_URL })
    client.on('error', err => console.error('Redis Client Error', err))
    client.connect().catch(err => console.error('Redis connection failed', err))
  }
  return client
}

export async function invalidateBookingCache(id: string): Promise<void> {
  const client = getClient()
  await client.del(`booking:${id}`)
}
