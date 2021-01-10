


class TestCaseExample(TestCase):
    def test_decorator(self):
        request = HttpRequest()
        # Set the required properties of your request
        function = lambda x: x
        decorator = login_required(function)
        response = decorator(request)
        self.assertRedirects(response)