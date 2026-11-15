import { NextApiRequest, NextApiResponse } from 'next'
import { getClient } from '../../lib/redis'
import { getBookingById } from '../../lib/db'
import { withAuth } from '../../lib/auth'

export default withAuth(async (req: NextApiRequest, res: NextApiResponse) => {
  const { id } = req.query
  if (!id || typeof id !== 'string') {
    return res.status(400).json({ error: 'Missing booking id' })
  }

  const cacheKey = `booking:${id}`
  const client = getClient()
  const cached = await client.get(cacheKey)
  if (cached) {
    return res.status(200).json(JSON.parse(cached))
  }

  const booking = await getBookingById(id)
  if (!booking) {
    return res.status(404).json({ error: 'Booking not found' })
  }

  await client.set(cacheKey, JSON.stringify(booking), 'EX', 300)
  return res.status(200).json(booking)
})
