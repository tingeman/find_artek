from django_cas_ng.views import LoginView as CasLoginView
from django.urls import reverse
from django.http import HttpResponse




class AdminCasLoginView(CasLoginView):




    def successful_login(self, request, next_page) -> HttpResponse:

        # if user is not 'adm-vicre', or 'thin', then let user know that they are not allowed to access the admin page
        if request.user.username != 'vicre' and request.user.username != 'thin':
            return HttpResponse("You are not allowed to access the admin page")

        next_page = reverse('admin:index')
        return super().successful_login(request, next_page)