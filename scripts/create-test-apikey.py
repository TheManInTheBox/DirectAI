"""Create a functional-test API key in the PostgreSQL api_keys table.

Run inside the api-server pod:
    kubectl cp scripts/create-test-apikey.py directai/<pod>:/tmp/create-test-apikey.py
    kubectl exec -n directai <pod> -- python /tmp/create-test-apikey.py

Prints the raw bearer token to stdout.  Store it in DIRECTAI_FUNC_TEST_KEY.
"""

import asyncio
import hashlib
import os
import secrets
import uuid


async def main() -> None:
    import asyncpg

    url = os.environ["DIRECTAI_DATABASE_URL"]
    conn = await asyncpg.connect(url)

    # Check table
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_keys')"
    )
    if not exists:
        print("ERROR: api_keys table does not exist")
        await conn.close()
        return

    # Generate key
    raw_token = "dai_sk_func_test_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    key_prefix = raw_token[:12]
    key_id = str(uuid.uuid4())

    # Find a user_id (use first user, or create a placeholder)
    user_id = await conn.fetchval("SELECT id FROM users LIMIT 1")
    if user_id is None:
        user_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO users (id, name, email) VALUES ($1, $2, $3)",
            user_id, "Functional Test User", "func-test@directai.dev",
        )
        print(f"Created test user: {user_id}")

    # Insert key
    await conn.execute(
        "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, name) VALUES ($1, $2, $3, $4, $5)",
        key_id, user_id, key_hash, key_prefix, "functional-test-key",
    )

    print(f"KEY_ID={key_id}")
    print(f"KEY_PREFIX={key_prefix}")
    print(f"BEARER_TOKEN={raw_token}")

    await conn.close()


asyncio.run(main())
