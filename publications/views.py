from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core import serializers
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.views import View

from publications.library import get_client_ip, is_private



from publications.forms import LoginForm

from publications.models import Publication, Topic, Feature

# Create your views here.


class BaseView(View):
    base_template = "publications/base.html"

    def get_context_data(self, **kwargs):
        context = {
            'base_template': self.base_template,
            # Other common context variables...
        }
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



        feature_colors = dict((
            ('PHOTO',             'red'),
            ('SAMPLE',            'green'),
            ('BOREHOLE',          'yellow'),
            ('GEOPHYSICAL DATA',  'blue'),
            ('FIELD MEASUREMENT', 'purple'),
            ('LAB MEASUREMENT',   'pink'),
            ('RESOURCE',          'brown'),
            ('OTHER',             'white')))

        features = Feature.objects.all()

        # Extract the points, lines, and polys from each feature
        feature_data = []
        for feature in features:


            related_publications = feature.get_related_publications()


            related_publications_data = []

            for publication in related_publications:
                related_publications_data.append({
                    'pk': publication.pk,
                    'number': publication.number,

                })


            feature_data.append({
                'points': feature.points.geojson if feature.points else "",
                'lines': feature.lines.geojson if feature.lines else "",
                'polys': feature.polys.geojson if feature.polys else "",
                'name': feature.name if feature.name else "",
                'type': feature.type if feature.type else "",
                'date': feature.date.strftime('%Y-%m-%d') if feature.date else "",
                'feature_pk': feature.pk,
                'related_publications'  : related_publications_data,
                })

        context = {

            'feature_data': feature_data,
            'feature_colors': feature_colors,
        }



        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)


















class ReportsView(BaseView):
    template_name = 'publications/reports.html'




    def get(self, request, **kwargs):
        # Get the topic from the GET parameters
        topic = request.GET.get('topic', None)


        # If the topic is not None, get the publications with that topic
        if topic is not None:
            # switch though each valid topic
            if topic == 'Infrastruktur':
                topic = Topic.objects.get(topic="Infrastruktur")
            if topic == 'Miljø':
                topic = Topic.objects.get(topic="Miljø")
            if topic == 'Energi':
                topic = Topic.objects.get(topic="Energi")
            if topic == 'Byggeri':
                topic = Topic.objects.get(topic="Byggeri")
            if topic == 'Geoteknik':
                topic = Topic.objects.get(topic="Geoteknik")
            if topic == 'Samfund':
                topic = Topic.objects.get(topic="Samfund")
            if topic == 'Råstoffer':
                topic = Topic.objects.get(topic="Råstoffer")

        if topic is not None:
            publications = Publication.objects.filter(publication_topics=topic)
        else:
            publications = Publication.objects.all()


        publications = publications.extra(select={'year': 'CAST(year AS INTEGER)'}).extra(order_by=['-year', '-number'])

        publications = publications.exclude(verified=False)

        context = {
            'publications': publications
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)








































class ReportView(BaseView):
    template_name = 'publications/report.html'

    def get(self, request, publication_id, **kwargs):
        publication = get_object_or_404(Publication, pk=publication_id)

        # If the report is not verified, only authenticated users can see it
        if not publication.verified and not request.user.is_authenticated:
            error = "You do not have permissions to access this publication!"

            return render(request, 'publications/access_denied.html', context = {'publication': publication, 'error': error})


        context = {
            'publication': publication,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)






























































class FeatureView(BaseView):


    def get(self, request, feature_id, **kwargs):

        feature = get_object_or_404(Feature, pk=feature_id)

        context = {
            'feature': feature,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, "publications/feature.html", context)







def feature(request, feature_id):
    feature = get_object_or_404(Feature, pk=feature_id)

    context = {
        'feature': feature,
    }

    return render(request, "publications/feature.html", context)























































































































class LoginView(BaseView):
    template_view = 'publications/login.html'

    # Check what is the IP address of the user



    def get(self, request, **kwargs):
        form = LoginForm()
        context = {'form': form}
        context.update(self.get_context_data(**kwargs))
        return render(request, self.template_view, context)

    def post(self, request, **kwargs):

        ip = get_client_ip(request)


        # Check if the IP address is in the list of allowed IP addresses
        if not is_private(ip):
                return render(request, 'publications/access_denied.html', context = {'error': 'Your IP address is not allowed to access this page!'})
                
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('frontpage')  # or wherever you want to redirect after successful login
            else:
                form.add_error(None, 'Authentication failed')

        context = {'form': form}
        context.update(self.get_context_data(**kwargs))
        return render(request, self.template_view, context)



































def map_data(request):
    features = Feature.objects.all()
    # q: in debug mode, how to loop through features and print out the attributes?
    # for feature in features:
    #     print(feature)
    serialized_features = serializers.serialize('json', features)
    return JsonResponse(serialized_features, safe=False)

