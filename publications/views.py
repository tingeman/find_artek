from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core import serializers
from django.http import JsonResponse
from django.contrib.auth import authenticate, login

from publications.forms import LoginForm

from publications.models import Publication, Topic, Feature

# Create your views here.








# create view for frontpage
def frontpage(request):
    return render(request, 'publications/frontpage.html')
    






















































def reports(request):

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

    return render(request, 'publications/reports.html', context)













































def report(request, publication_id):


    publication = get_object_or_404(Publication, pk=publication_id)

    # If the report is not verified, only authenticated users can see it
    if not publication.verified and not request.user.is_authenticated:
        error = "You do not have permissions to access this publication!"

        return render(request, 'publications/access_denied.html', context = {'publication': publication, 'error': error})


    context = {
        'publication': publication,
    }


    return render(request, "publications/report.html", context)



























def map(request):
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

        # 

        related_publications_data = [

        ]

        for publication in related_publications:
            related_publications_data.append({
                'pk': publication.pk,
                'number': publication.number,

            })

        # for each 



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

    return render(request, 'publications/map.html', context=context)











































def map_data(request):
    features = Feature.objects.all()
    # q: in debug mode, how to loop through features and print out the attributes?
    # for feature in features:
    #     print(feature)
    serialized_features = serializers.serialize('json', features)
    return JsonResponse(serialized_features, safe=False)









































def feature(request, feature_id):
    feature = get_object_or_404(Feature, pk=feature_id)

    context = {
        'feature': feature,
    }

    return render(request, "publications/feature.html", context)




























def login_view(request):
    if request.method == 'POST':
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
    else:
        form = LoginForm()
    return render(request, 'publications/login.html', {'form': form})




