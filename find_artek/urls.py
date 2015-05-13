from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib.gis import admin
import settings

from find_artek.publications import signals   # In order to hook into the authentications

admin.autodiscover()


import logging
logger = logging.getLogger(__name__)
logger.debug('TEST: in urls.py')


"""
Prefferred url design is e.g. pubs/report/XXX/edit/
                              pubs/report/add/
                              etc.

Should design new like this
Rework old urls into this design, will require change of templates and views.

Furthermore should implement naming of urls, to allow reverse url matchin in
templates.

f.ex.:
url(r'^$', 'find_artek.views.index', name='index'),

in a template we could insert this link by:

{% url 'index' %}


and:

url(r'^pubs/detail/(?P<pub_id>\d+)/$', 'find_artek.publications.views.detail', name='pubs-detail')

would for the publication with id 121 become:

{% url 'pubs-detail' 121 %}

"""


urlpatterns = patterns('',
    # Examples:
    url(r'^$', 'find_artek.views.index', name='index'),
    url(r'^test/$', 'find_artek.views.test', name='test'),
    url(r'^pubs/$', 'find_artek.publications.views.index'),
    url(r'^pubs/search/$', 'find_artek.publications.views.search'),
    url(r'^pubs/frontpage/$', 'find_artek.publications.views.frontpage'),
    url(r'^pubs/overview/$', 'find_artek.publications.views.overview'),
    url(r'^pubs/detail/(?P<pub_id>\d+)/$', 'find_artek.publications.views.detail'),
    url(r'^pubs/person/(?P<person_id>\d+)/$', 'find_artek.publications.views.person_detail'),
    url(r'^pubs/feature/(?P<feature_id>\d+)/$', 'find_artek.publications.views.feature_detail'),
    url(r'^pubs/feature/(?P<feature_id>\d+)/delete/$', 'find_artek.publications.views.delete_feature'),
    url(r'^pubs/all/$', 'find_artek.publications.views.publist'),
    url(r'^pubs/publist/$', 'find_artek.publications.views.publist'),
    url(r'^pubs/list/pubs/$', 'find_artek.publications.views.publist'),
    url(r'^pubs/list/persons/$', 'find_artek.publications.views.person_list'),
    url(r'^pubs/keywords/list/$', 'find_artek.publications.views.keyword_list'),
    url(r'^pubs/studreps/$', 'find_artek.publications.views.studreps'),
    url(r'^pubs/featlist/$', 'find_artek.publications.views.featlist'),
    url(r'^pubs/report/(?P<pub_id>\d+)/$', 'find_artek.publications.views.detail'),
    url(r'^pubs/report/(?P<pub_id>\d+)/add/feature/digitize/$', 'find_artek.publications.views.add_edit_feature'),
    url(r'^pubs/report/(?P<pub_id>\d+)/add/feature/$', 'find_artek.publications.views.add_feature_choice'),
    url(r'^pubs/report/(?P<pub_id>\d+)/add/feature/digitize/$', 'find_artek.publications.views.add_edit_feature'),
    url(r'^pubs/report/(?P<pub_id>\d+)/add/features/from_file/$', 'find_artek.publications.views.add_features_from_file'),
    url(r'^pubs/report/(?P<pub_id>\d+)/add/feature/online_form/$', 'find_artek.publications.views.add_edit_feature_wcoords'),
    url(r'^pubs/add/$', 'find_artek.publications.views.add_menu'),
    url(r'^pubs/add/report/$', 'find_artek.publications.views.add_edit_report'),
    url(r'^pubs/add/pubs_from_file/$', 'find_artek.publications.views.add_pubs_from_file'),
    url(r'^pubs/add/features_from_file/$', 'find_artek.publications.views.add_features_from_file'),
    url(r'^pubs/add/person/$', 'find_artek.publications.views.add_edit_person'),
    #url(r'^pubs/add/person/$', 'find_artek.publications.views.add_person_ajax_test'),
    url(r'^pubs/add/feature/$', 'find_artek.publications.views.add_edit_feature'),
    url(r'^pubs/validate/features_from_file/$', 'find_artek.publications.views.validate_features_from_file'),
    url(r'^pubs/edit/report/(?P<pub_id>\d+)/$', 'find_artek.publications.views.add_edit_report'),
    url(r'^pubs/edit/report/(?P<pub_id>\d*)/upload/(?P<batch_tag>[A-Z0-9_]+)/$', 'find_artek.publications.views.upload_report_files'),
    url(r'^pubs/add/report/upload/(?P<batch_tag>[A-Z0-9_]+)/$', 'find_artek.publications.views.upload_report_files'),
    url(r'^pubs/edit/feature/(?P<feat_id>\d+)/$', 'find_artek.publications.views.add_edit_feature'),
    url(r'^pubs/edit/person/(?P<person_id>\d+)/$', 'find_artek.publications.views.add_edit_person'),
    url(r'^pubs/report/(?P<pub_id>\d*)/delete/$', 'find_artek.publications.views.delete_publication'),
    url(r'^pubs/report/(?P<pub_id>\d*)/delete_all_features/$', 'find_artek.publications.views.delete_publication_features'),
    url(r'^pubs/report/(?P<pub_id>\d*)/delete_reportfile/$', 'find_artek.publications.views.delete_publication_file'),
    url(r'^pubs/report/(?P<pub_id>\d*)/delete_appendixfile/(?P<apx_id>[A-Z0-9_]+)/$', 'find_artek.publications.views.delete_publication_appendix'),
    url(r'^pubs/report/(?P<pub_id>\d*)/upload/$', 'find_artek.publications.views.upload_report_files'),
    url(r'^pubs/person/(?P<person_id>\d+)/delete/$', 'find_artek.publications.views.person_delete'),
    url(r'^pubs/person/(?P<person_id>\d+)/merge/$', 'find_artek.publications.views.person_merge'),
    url(r'^pubs/person/ajax/$', 'find_artek.publications.views.person_ajax'),
    url(r'^pubs/person/ajax/search/$', 'find_artek.publications.views.person_ajax_search'),
    url(r'^pubs/person/ajax/add/$', 'find_artek.publications.views.add_person_ajax'),
    url(r'^pubs/person/ajax/check/$', 'find_artek.publications.views.check_person_ajax'),
    url(r'^pubs/feature/(?P<feat_id>\d*)/upload_files/$', 'find_artek.publications.views.upload_feature_files', name='pubs-upload_feature_files'),
    url(r'^pubs/feature/(?P<feat_id>\d*)/upload_images/$', 'find_artek.publications.views.upload_feature_images', name='pubs-upload_feature_images'),
    url(r'^pubs/ajax/search/keyword/$', 'find_artek.publications.views.ajax_keyword_search'),
    url(r'^pubs/ajax/search/topic/$', 'find_artek.publications.views.ajax_topic_search'),
    url(r'^pubs/ajax/list/reports/$', 'find_artek.publications.views.ajax_list_reports'),
    url(r'^pubs/test/keywords/$', 'find_artek.publications.views.test_keyword_tag'),
    url(r'^pubs/verify/report/(?P<pub_id>\d+)/$', 'find_artek.publications.views.verify_report'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^accounts/logout/$', 'find_artek.publications.views.logout'),
    url(r'^pubs/test/images/upload/$', 'find_artek.publications.views.multi_uploader_image_view'),
    url(r'^db/backup/$', 'find_artek.views.db_backup'),
    url(r'', include('multiuploader.urls')),
    url(r'^i18n/', include('django.conf.urls.i18n')),

)

if settings.DEBUG:
    urlpatterns += patterns('',
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {
            'document_root': settings.MEDIA_ROOT,
        }),
   )


handler404 = 'find_artek.views.error_404_view'
handler500 = 'find_artek.views.error_500_view'
