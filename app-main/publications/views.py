from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core import serializers
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.views import View
from django.urls import reverse

from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from publications.library import get_client_ip, is_private
from publications.forms import LoginForm
from publications.models import Publication, Topic, Feature, Person
#from .forms import PublicationForm


# Create your views here.




class BaseView(View):
    base_template = "publications/base.html"

    def get_context_data(self, **kwargs):
        # context = super().get_context_data(**kwargs)    # View class has no method get_context_data
        context = {
            'base_template': self.base_template,
            # Other common context variables...
        }
        print('In BaseView')
        print(context.keys())
        return context
    
    def get(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        return render(request, self.base_template, context)


class BaseDetailView(DetailView, BaseView):
    def get_context_data(self, **kwargs):
        # Get the context from BaseView
        context = super().get_context_data(**kwargs)

        # Get the context from BaseView
        base_context = BaseView.get_context_data(self, **kwargs)
        
        # Combine the contexts
        context.update(base_context)
        
        return context








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
        # Extract the 'topic' query parameter from the request
        topic = request.GET.get('topic', None)

        context = {
            'topic': topic,  # Add the topic to the context
        }

        # Update the context with additional data
        context.update(self.get_context_data(**kwargs))

        # Render the template with the context
        return render(request, self.template_name, context)

























class PersonsView(BaseView):
    template_name = 'publications/persons.html'

    def get(self, request, **kwargs):
        
        person_list = Person.objects.all().order_by('last', 'first')  # .order_by('-year').order_by('number')

        context = {
            'pers_list': person_list,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)
































# class ReportView(BaseView):
#     template_name = 'publications/report.html'

#     def get(self, request, publication_id, **kwargs):
#         publication = get_object_or_404(Publication, pk=publication_id)

#         associated_features = Feature.objects.filter(publications=publication)

#         # If the report is not verified, only authenticated users can see it
#         if not publication.verified and not request.user.is_authenticated:
#             error = "You do not have permissions to access this publication!"

#             context = {'publication': publication, 'error': error}
#             context.update(self.get_context_data(**kwargs))

#             return render(request, 'publications/access_denied.html', context=context)


#         context = {
#             'publication_id': publication_id,
#             'associated_features': associated_features,
#             'publication': publication,
#         }

#         context.update(self.get_context_data(**kwargs))

#         return render(request, self.template_name, context)




class ReportView(BaseDetailView):
    model = Publication
    template_name = 'publications/report.html'
    context_object_name = 'publication'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        associated_features = Feature.objects.filter(publications=self.object)

        context.update({'associated_features': associated_features})
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.verified and not request.user.is_authenticated:
            context = self.get_context_data(object=self.object)
            context['error'] = "You do not have permissions to access this publication!"
            return render(request, 'publications/access_denied.html', context=context)
        return super().get(request, *args, **kwargs)




# class ReportView(BaseView, TemplateView):
#     template_name = 'publications/report.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)

#         pk = self.kwargs.get('pk')
#         publication = get_object_or_404(Publication, pk=pk)
#         associated_features = Feature.objects.filter(publications=publication)

#         context.update({
#             'pk': pk,
#             'associated_features': associated_features,
#             'publication': publication,
#         })
#         return context

    # def get(self, request, *args, **kwargs):
    #     context = self.get_context_data(**kwargs)
    #     publication = context['publication']
    #     print(context.keys())

    #     # If the report is not verified, only authenticated users can see it
    #     if not publication.verified and not request.user.is_authenticated:
    #         error = "You do not have permissions to access this publication!"
    #         context['error'] = error
    #         return render(request, 'publications/access_denied.html', context=context)

    #     return self.render_to_response(context)





@method_decorator(login_required, name='dispatch')
class AddEditReportView(BaseView, CreateView, UpdateView):
    model = Publication
    #form_class = PublicationForm
    template_name = 'publications/add_edit_report.html'

    def get_object(self):
        publication_id = self.kwargs.get('publication_id')
        if publication_id:
            return get_object_or_404(Publication, pk=publication_id)
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object:
            context['associated_features'] = self.object.feature_set.all()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        # Add any custom logic here
        return response

    def get_success_url(self):
        return reverse('report', kwargs={'pk': self.object.pk})





























class PersonView(BaseDetailView):
    model = Person
    template_name = 'publications/person.html'
    context_object_name = 'person'



























































class FeatureView(BaseDetailView):
    model = Feature
    template_name = 'publications/feature.html'
    context_object_name = 'feature'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        geometry = self.object.points or self.object.lines or self.object.polys
        context.update({'geometry': geometry})
        return context



























































































































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
        return redirect('frontpage')






























# def map_data(request):
#     features = Feature.objects.all()
#     # q: in debug mode, how to loop through features and print out the attributes?
#     # for feature in features:
#     #     print(feature)
#     serialized_features = serializers.serialize('json', features)
#     return JsonResponse(serialized_features, safe=False)

