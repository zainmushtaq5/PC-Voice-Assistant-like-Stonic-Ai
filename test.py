try:
    import app
    print('imported')
except Exception as e:
    import traceback
    traceback.print_exc()
