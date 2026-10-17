def test_function_app_exports_handlers():
    import function_app

    assert callable(function_app.chat)
    assert callable(function_app.health)
    assert function_app.app is not None
