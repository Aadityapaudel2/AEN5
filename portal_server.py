from browser.portal_server import app


if __name__ == "__main__":
    import uvicorn
    from browser.portal_server import cfg

    uvicorn.run("browser.portal_server:app", host=cfg.host, port=cfg.port, reload=False)
