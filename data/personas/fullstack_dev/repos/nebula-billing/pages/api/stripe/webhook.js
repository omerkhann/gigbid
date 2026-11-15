import { buffer } from "micro";
import Cors from "micro-cors";
import Stripe from "stripe";
import { connectToDatabase } from "../../lib/db";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: "2023-10-16" });

export const config = { api: { bodyParser: false } };

const cors = Cors({ allowMethods: ["POST", "HEAD"] });

async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }
  const sig = req.headers["stripe-signature"]; // eslint-disable-line
  let event;
  try {
    const buf = await buffer(req);
    event = stripe.webhooks.constructEvent(buf, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error("Webhook signature verification failed", err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  const { data, type } = event;
  const { db } = await connectToDatabase();

  switch (type) {
    case "checkout.session.completed":
      const session = data.object;
      await db.collection("subscriptions").insertOne({
        userId: session.client_reference_id,
        stripeSubscriptionId: session.subscription,
        status: session.payment_status,
        createdAt: new Date(),
      });
      break;
    case "customer.subscription.updated":
      await db.collection("subscriptions").updateOne(
        { stripeSubscriptionId: data.object.id },
        { $set: { status: data.object.status } }
      );
      break;
    case "customer.subscription.deleted":
      await db.collection("subscriptions").deleteOne({ stripeSubscriptionId: data.object.id });
      break;
    default:
      console.log(`Unhandled event type ${type}`);
  }
  res.json({ received: true });
}

export default cors(handler);
