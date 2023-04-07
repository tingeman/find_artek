from django.http import HttpResponse
from django.shortcuts import render

from publications.models import Publication

# Create your views here.


# create view for frontpage
def frontpage(request):
    return render(request, 'publications/frontpage.html')


def publist(request):

    # get all publications from database
    publications = Publication.objects.all()

    publications = publications.extra(select={'year': 'CAST(year AS INTEGER)'}).extra(order_by=['-year', '-number'])


    context = {
        'publications': publications
    }

    return render(request, 'publications/publist.html', context)


