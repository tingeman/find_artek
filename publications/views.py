from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core import serializers
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.views import View

from publications.library import get_client_ip, is_private



from publications.forms import LoginForm

from publications.models import Publication, Topic, Feature, Person

# Create your views here.


class BaseView(View):
    base_template = "publications/base.html"

    def get_context_data(self, **kwargs):
        context = {
            'base_template': self.base_template,
            # Other common context variables...
        }
        return context
    
    def get(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        return render(request, self.base_template, context)










class FrontPageView(BaseView):

    template_name = 'publications/frontpage.html'

    def get(self, request, **kwargs):

        context = {
        }

        context.update(self.get_context_data(**kwargs))
        return render(request, self.template_name, context)




















































class MapView(BaseView): 
    template_name = 'publications/map.html'
    def get(self, request, **kwargs):

        context = {
        }
        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)


















class ReportsView(BaseView):
    template_name = 'publications/reports.html'

    def get(self, request, **kwargs):


        context = {
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)







class PersonsView(BaseView):
    template_name = 'publications/persons.html'

    def get(self, request, **kwargs):


        context = {
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)
































class ReportView(BaseView):
    template_name = 'publications/report.html'

    def get(self, request, publication_id, **kwargs):
        publication = get_object_or_404(Publication, pk=publication_id)

        associated_features = Feature.objects.filter(publications=publication)

        # If the report is not verified, only authenticated users can see it
        if not publication.verified and not request.user.is_authenticated:
            error = "You do not have permissions to access this publication!"

            return render(request, 'publications/access_denied.html', context = {'publication': publication, 'error': error})


        context = {
            'publication_id': publication_id,
            'associated_features': associated_features,
            'publication': publication,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)



class PersonView(BaseView):
    template_name = 'publications/person.html'

    def get(self, request, person_id, **kwargs):
        person = get_object_or_404(Person, pk=person_id)

        context = {
            'person': person,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)


























































class FeatureView(BaseView):


    def get(self, request, feature_id, **kwargs):

        feature = get_object_or_404(Feature, pk=feature_id)

        geometry = feature.points or feature.lines or feature.polys

        


        context = {
            'feature': feature,
            'geometry': geometry,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, "publications/feature.html", context)




























































































































class LoginView(BaseView):
    
    
    template_view = 'publications/login.html'

    # Check what is the IP address of the user
    def get(self, request, **kwargs):
        
        context = self.get_context_data(**kwargs)
        return render(request, 'publications/under_construction.html', context)
    

        form = LoginForm()
        context = {'form': form}
        context.update(self.get_context_data(**kwargs))
        return render(request, self.template_view, context)

    # def post(self, request, **kwargs):
        
    #     ip = get_client_ip(request)


    #     # Check if the IP address is in the list of allowed IP addresses
    #     if not is_private(ip):
    #             return render(request, 'publications/access_denied.html', context = {'error': 'Your IP address is not allowed to access this page!'})
                
    #     form = LoginForm(request.POST)
    #     if form.is_valid():
    #         username = form.cleaned_data['username']
    #         password = form.cleaned_data['password']
    #         user = authenticate(request, username=username, password=password)
    #         if user is not None:
    #             login(request, user)
    #             return redirect('frontpage')  # or wherever you want to redirect after successful login
    #         else:
    #             form.add_error(None, 'Authentication failed')

    #     context = {'form': form}
    #     context.update(self.get_context_data(**kwargs))
    #     return render(request, self.template_view, context)



































# def map_data(request):
#     features = Feature.objects.all()
#     # q: in debug mode, how to loop through features and print out the attributes?
#     # for feature in features:
#     #     print(feature)
#     serialized_features = serializers.serialize('json', features)
#     return JsonResponse(serialized_features, safe=False)

