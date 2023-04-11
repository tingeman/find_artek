from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template import RequestContext

from publications.models import Publication

# Create your views here.








# create view for frontpage
def frontpage(request):
    return render(request, 'publications/frontpage.html')






















































def publist(request):

    # get all publications from database
    publications = Publication.objects.all()

    publications = publications.extra(select={'year': 'CAST(year AS INTEGER)'}).extra(order_by=['-year', '-number'])

    publications = publications.exclude(verified=False)

    context = {
        'publications': publications
    }

    return render(request, 'publications/publist.html', context)













































def detail(request, pub_id):


    p = get_object_or_404(Publication, pk=pub_id)

    # If the report is not verified, only authenticated users can see it
    if not p.verified and not request.user.is_authenticated:
        error = "You do not have permissions to access this publication!"

        return render(request, 'publications/access_denied.html', context = {'pub': p, 'error': error})




    context = {
        'pub': p,
    }

    return render(request, "publications/detail.html", context)





