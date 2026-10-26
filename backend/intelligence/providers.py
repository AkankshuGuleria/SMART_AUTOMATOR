"""
intelligence/providers.py — what an environment variable is for, and how to get it.

Used by the project profile (to label requirements) and the Needs inbox (to
give step-by-step instructions). Matching is by variable-name prefix/pattern.
"""

from __future__ import annotations

import re

# (pattern, provider, kind, how-to steps, docs url)
PROVIDERS: list[tuple[str, str, str, list[str], str]] = [
    (r"^STRIPE_", "Stripe", "api_key", [
        "Sign in at dashboard.stripe.com (use Test mode while developing).",
        "Developers → API keys: copy the Secret key (sk_test_…) and Publishable key (pk_test_…).",
        "For webhooks: Developers → Webhooks → add endpoint, then copy the signing secret (whsec_…).",
    ], "https://dashboard.stripe.com/apikeys"),
    (r"^OPENAI_", "OpenAI", "api_key", [
        "Sign in at platform.openai.com → API keys → Create new secret key.",
        "Copy it once (it is shown only once).",
    ], "https://platform.openai.com/api-keys"),
    (r"^ANTHROPIC_", "Anthropic", "api_key", [
        "Sign in at console.anthropic.com → Settings → API keys → Create key.",
    ], "https://console.anthropic.com/settings/keys"),
    (r"^(NEXT_PUBLIC_)?SUPABASE_", "Supabase", "api_key", [
        "Open your project at supabase.com/dashboard → Project Settings → API.",
        "Copy the Project URL and the anon public key; the service_role key is server-only.",
    ], "https://supabase.com/dashboard"),
    (r"^(NEXT_PUBLIC_)?FIREBASE_|^VITE_FIREBASE_", "Firebase", "api_key", [
        "console.firebase.google.com → Project settings → General → Your apps → SDK setup and configuration.",
        "Copy the config values (apiKey, authDomain, projectId…).",
    ], "https://console.firebase.google.com/"),
    (r"^(NEXT_PUBLIC_)?CLERK_", "Clerk", "api_key", [
        "dashboard.clerk.com → your application → API keys.",
        "Copy the Publishable key and the Secret key.",
    ], "https://dashboard.clerk.com/"),
    (r"^NEXTAUTH_|^AUTH_SECRET$", "NextAuth / Auth.js", "secret", [
        "Generate a random secret: run `npx auth secret` or `openssl rand -base64 32`.",
        "Set NEXTAUTH_URL to your app URL (http://localhost:3000 in development).",
    ], "https://authjs.dev/getting-started/deployment"),
    (r"^(DATABASE_URL|POSTGRES_URL|PG_|POSTGRES_)", "PostgreSQL", "connection_string", [
        "Local: install PostgreSQL or run `docker run -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres`.",
        "Hosted: create a database on Neon, Supabase or Railway and copy its connection string.",
        "Format: postgresql://user:password@host:5432/dbname",
    ], "https://neon.tech/docs/connect/connect-from-any-app"),
    (r"^COCKROACH", "CockroachDB", "connection_string", [
        "cockroachlabs.cloud → your cluster → Connect → choose your language/driver.",
        "Copy the connection string (includes sslmode=verify-full).",
    ], "https://cockroachlabs.cloud/"),
    (r"^(MONGODB_|MONGO_)", "MongoDB", "connection_string", [
        "MongoDB Atlas → Database → Connect → Drivers, copy the mongodb+srv:// string.",
        "Local: `docker run -p 27017:27017 mongo` and use mongodb://localhost:27017/dbname.",
    ], "https://cloud.mongodb.com/"),
    (r"^REDIS_|^UPSTASH_", "Redis", "connection_string", [
        "Local: `docker run -p 6379:6379 redis` → redis://localhost:6379.",
        "Hosted: create a database on Upstash and copy the REST/redis URL and token.",
    ], "https://console.upstash.com/"),
    (r"^AWS_", "AWS", "api_key", [
        "IAM console → Users → your user → Security credentials → Create access key.",
        "Prefer a least-privilege user; set AWS_REGION too.",
    ], "https://console.aws.amazon.com/iam/"),
    (r"^(GOOGLE_|GCP_|GEMINI_)", "Google", "api_key", [
        "Gemini: aistudio.google.com → Get API key. Other Google APIs: console.cloud.google.com → APIs & Services → Credentials.",
    ], "https://aistudio.google.com/app/apikey"),
    (r"^GITHUB_", "GitHub", "api_key", [
        "github.com → Settings → Developer settings → Personal access tokens (fine-grained).",
        "For OAuth apps: Developer settings → OAuth Apps → client ID and secret.",
    ], "https://github.com/settings/tokens"),
    (r"^(RESEND_)", "Resend", "api_key", ["resend.com → API Keys → Create API key."], "https://resend.com/api-keys"),
    (r"^(SENDGRID_)", "SendGrid", "api_key", ["app.sendgrid.com → Settings → API Keys."], "https://app.sendgrid.com/settings/api_keys"),
    (r"^(TWILIO_)", "Twilio", "api_key", ["console.twilio.com → Account info: Account SID and Auth Token."], "https://console.twilio.com/"),
    (r"^GROQ_", "Groq", "api_key", ["console.groq.com → API Keys → Create API key."], "https://console.groq.com/keys"),
    (r"^OPENROUTER_", "OpenRouter", "api_key", ["openrouter.ai → Keys → Create key."], "https://openrouter.ai/keys"),
    (r"^COHERE_", "Cohere", "api_key", ["dashboard.cohere.com → API keys."], "https://dashboard.cohere.com/api-keys"),
    (r"^CLOUDINARY_", "Cloudinary", "api_key", ["cloudinary.com console → Dashboard: cloud name, API key and secret."], "https://console.cloudinary.com/"),
]

SECRET_HINT = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|PASS|PRIVATE|CREDENTIAL)", re.I)
URL_HINT = re.compile(r"(URL|URI|DSN|HOST|CONNECTION|ENDPOINT)", re.I)


def describe(var: str) -> dict:
    """Provider, kind (api_key | connection_string | secret | config) and instructions for *var*."""
    for pattern, provider, kind, steps, url in PROVIDERS:
        if re.search(pattern, var):
            return {"provider": provider, "kind": kind, "steps": steps, "docs_url": url}
    if SECRET_HINT.search(var):
        kind = "secret"
    elif URL_HINT.search(var):
        kind = "connection_string"
    else:
        kind = "config"
    return {
        "provider": None,
        "kind": kind,
        "steps": [f"Find the value for {var} in the service it belongs to, or ask the project owner."],
        "docs_url": None,
    }
