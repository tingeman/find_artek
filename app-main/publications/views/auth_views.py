
# === Standard library imports ===

# === Django imports ===
from django.contrib.auth import logout
from django.shortcuts import redirect
from publications.views.base_views import BaseView 



# class LoginView(BaseView):
#     template_view = 'publications/login.html'

#     # Check what is the IP address of the user
#     def get(self, request, **kwargs):

#         form = LoginForm()
#         context = {'form': form}
#         context.update(self.get_context_data(**kwargs))
#         return render(request, self.template_view, context)

#     def post(self, request, **kwargs):
        
#         ip = get_client_ip(request)

#         # Check if the IP address is in the list of allowed IP addresses
#         if not is_private(ip):
#                 return render(request, 'publications/access_denied.html', context = {'error': 'Your IP address is not allowed to access this page!'})
                
#         form = LoginForm(request.POST)
#         if form.is_valid():
#             username = form.cleaned_data['username']
#             password = form.cleaned_data['password']

#             user = authenticate(request, username=username, password=password)

#             if user is not None:
#                 login(request, user)
#                 return redirect('frontpage')  # or wherever you want to redirect after successful login
#             else:
#                 form.add_error(None, 'Authentication failed')

#         context = {'form': form}
#         context.update(self.get_context_data(**kwargs))
#         return render(request, self.template_view, context)



class LogoutView(BaseView):
    def get(self, request, **kwargs):
        logout(request)
        return redirect('publications:frontpage')







