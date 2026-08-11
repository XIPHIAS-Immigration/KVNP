# Stripe Billing setup

KVNP uses a flat-rate recurring Stripe Price in Canadian dollars. Checkout is hosted by Stripe. Customers pay first, choose their KVNP account credentials after Stripe confirms payment, and are then signed in automatically.

## Customer flow

1. The visitor chooses **Pay securely with Stripe** without creating an account first.
2. Stripe collects the payment method and billing email on hosted Checkout.
3. Stripe returns the browser to `/activate` while also sending a signed webhook.
4. KVNP verifies the Checkout Session server-side and requires the matching one-use HttpOnly browser claim.
5. A new customer chooses a name and password. If the payment email already has an account, that account's existing password is required.
6. KVNP links the active subscription, creates a login session and opens the customer's workspace.

The Checkout Session ID by itself cannot activate a purchase, and account details are never accepted before payment is verified.

## 1. Create the sandbox plan

1. Open Stripe Dashboard in **Sandbox** mode.
2. Create a product named `KVNP Studio membership`.
3. Add a recurring price in **CAD** and choose the billing interval.
4. Copy the resulting `price_...` ID. Do not copy a Product ID into `STRIPE_PRICE_ID`.
5. Configure the displayed amount with `KVNP_SUBSCRIPTION_PRICE_LABEL`, for example `CAD 14.99 / month`.

The server retrieves the Price before opening Checkout and refuses inactive, non-recurring, or non-CAD Prices.

## 2. Configure the customer portal

In **Settings > Billing > Customer portal**, enable payment-method updates, invoice history and subscription cancellation. Set the business name, support URL and KVNP branding there as well.

## 3. Create the webhook

Create a sandbox webhook endpoint:

`https://passport.kvnp.ca/api/stripe/webhook`

Subscribe it to:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Copy its `whsec_...` signing secret into the server's `.env`, never into Git or browser code.

## 4. Configure server secrets

Set these values in `~/KVNP/.env` on the server:

```ini
KVNP_PAYMENT_MODE=stripe
KVNP_COMMERCE_ENFORCED=true
KVNP_PUBLIC_URL=https://passport.kvnp.ca
KVNP_COOKIE_SECURE=true
KVNP_SUBSCRIPTION_PRICE_MINOR=500
KVNP_SUBSCRIPTION_PRICE_LABEL=CAD XX.XX / month
STRIPE_PRICE_ID=price_replace_me
STRIPE_CURRENCY=CAD
STRIPE_WEBHOOK_SECRET=replace_on_server
STRIPE_RESTRICTED_KEY=replace_on_server
```

For the first sandbox test, `STRIPE_SECRET_KEY` is also supported. Prefer a restricted key for production and leave the unused key variable blank. The server does not need a publishable key because card entry happens on Stripe-hosted Checkout.

The restricted key needs only the Stripe resources used by this service: Prices read, Checkout Sessions write, Billing Portal Sessions write, Subscriptions read and Customers read. Test it in sandbox and add a permission only if Stripe reports a denied operation.

## 5. Deploy

After the code is pushed, rebuild the same GPU/PostgreSQL stack:

```bash
cd ~/KVNP
git pull --ff-only
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.postgres.yaml up -d --build
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.postgres.yaml ps
curl -fsS https://passport.kvnp.ca/api/health
```

Open `/pricing` in a private browser window, complete a sandbox checkout, create the account on `/activate`, and confirm `/account` shows an active membership. Then verify `/admin` reports the user, subscription and payment.

If Checkout displays `temporarily unavailable`, inspect the sanitized provider error:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.postgres.yaml logs --tail=120 app | grep "Stripe Checkout"
```

## Safety notes

- The success URL never grants access. KVNP verifies payment from the signed webhook or directly from Stripe's server API.
- Webhook event IDs are stored so retries do not provision twice.
- Anonymous purchases use a 48-hour, one-use, hashed checkout claim stored in an HttpOnly `SameSite=Lax` cookie.
- Stripe Tax is intentionally not enabled until KVNP confirms its Canadian tax registrations and collection obligations.
- Do not email passwords. Customers choose their own password only after payment confirmation; KVNP stores its Argon2 hash.
- Before switching to live mode, create a separate live Price, webhook secret and restricted key.
