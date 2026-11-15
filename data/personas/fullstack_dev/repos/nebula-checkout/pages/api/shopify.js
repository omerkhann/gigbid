import { Shopify } from '@shopify/shopify-api';

const shopify = new Shopify.Clients.Rest(process.env.SHOPIFY_SHOP_NAME, process.env.SHOPIFY_ACCESS_TOKEN);

export default async function handler(req, res) {
  try {
    const { query } = req;
    const { title, limit = 10 } = query;
    const products = await shopify.get({ path: 'products', query: { title, limit } });
    res.status(200).json(products.body.products);
  } catch (error) {
    console.error('Shopify API error:', error);
    res.status(500).json({ error: 'Failed to fetch products' });
  }
}
