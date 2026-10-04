from core import setup_tools


def test_fetch_clerk_key_rewrites_only_that_line(tmp_path, monkeypatch, rsa_public_pem):
    env = tmp_path / ".env"
    env.write_text(
        "APP_ENV=development\nCLERK_PUBLISHABLE_KEY=pk_test_ZmFtb3VzLWhvcm5ldC0yODM5LmNsZXJrLmFjY291bnRzLmRldiQ\n"
        'CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----"\nSHOP_NAME=Saree\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_tools, "fetch_public_key_pem", lambda pk: rsa_public_pem.strip())
    host = setup_tools.fetch_clerk_key(env)
    assert host == "famous-hornet-2839.clerk.accounts.dev"
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "APP_ENV=development" and lines[-1] == "SHOP_NAME=Saree"
    jwt_line = next(line for line in lines if line.startswith("CLERK_JWT_KEY="))
    assert jwt_line == 'CLERK_JWT_KEY="' + rsa_public_pem.strip().replace("\n", "\\n") + '"'
