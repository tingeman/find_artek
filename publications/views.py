from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template import RequestContext

from publications.models import Publication, Topic

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
    return render(request, 'publications/map.html')