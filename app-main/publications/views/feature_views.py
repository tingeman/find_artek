# === Standard library imports ===
import json
import traceback

# === Django imports ===
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator

# TODO: Should we inherit from BaseFormView instead?
from django.views.generic import FormView, DeleteView

# === Django GIS imports ===
from django.contrib.gis.geos import Point, MultiPoint

# === Project-specific imports ===
from publications import models
from publications.forms import AddFeatureByCoordinatesForm, AddFeatureByMap
#from publications.forms.mixins import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm

from publications.views.base_views import BaseView, BaseDetailView, BaseFormView 
# Create your views here.





class MapView(BaseView): 
    template_name = 'publications/map.html'
    def get(self, request, **kwargs):

        context = {
        }
        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)


class FeatureView(BaseDetailView):
    model = models.Feature
    template_name = 'publications/feature.html'
    context_object_name = 'feature'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        geometry = self.object.points or self.object.lines or self.object.polys
        context.update({'geometry': geometry})
        return context



@method_decorator(login_required, name='dispatch')
class AddFeatureCoordinatesView(BaseFormView):
    """View for adding a point feature with known coordinates"""
    template_name = 'publications/add_feature_coordinates.html'
    form_class = AddFeatureByCoordinatesForm
    
    def dispatch(self, request, *args, **kwargs):
        """Add debugging for all requests"""
        print(f"AddFeatureCoordinatesView.dispatch: {request.method} request received")
        print(f"POST data: {request.POST}")
        return super().dispatch(request, *args, **kwargs)
    
    def get_publication(self):
        """Get the publication this feature will be associated with"""
        report_pk = self.kwargs.get('report_pk')
        return get_object_or_404(models.Publication, pk=report_pk)
    
    def get_context_data(self, **kwargs):
        print("AddFeatureCoordinatesView.get_context_data called")
        context = super().get_context_data(**kwargs)
        context['publication'] = self.get_publication()
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests with debugging"""
        print(f"AddFeatureCoordinatesView.post called with data: {request.POST}")
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Process valid form and create the feature"""
        print(f"AddFeatureCoordinatesView.form_valid called with cleaned_data: {form.cleaned_data}")
        
        try:
            print("Step 1: Getting publication...")
            publication = self.get_publication()
            print(f"Publication: {publication}")
            
            print("Step 2: Creating feature instance...")
            # Create the feature instance
            feature = form.save(commit=False)
            feature.created_by = self.request.user
            feature.modified_by = self.request.user
            
            print(f"Feature instance created: {feature}")
            print(f"Feature date: {feature.date}")
            
            print("Step 3: Getting coordinate data...")
            # Get coordinate data
            x_coord = form.cleaned_data['x_coordinate']
            y_coord = form.cleaned_data['y_coordinate']
            srid = int(form.cleaned_data['spatial_reference_system'])
            print(f"Coordinates: x={x_coord}, y={y_coord}, srid={srid}")
            
            print("Step 4: Creating Point geometry...")
            # Create the geometry
            point = Point(float(x_coord), float(y_coord), srid=srid)
            print(f"Point created: {point}")
            
            print("Step 5: Converting to MultiPoint...")
            # Convert to MultiPoint for storage (following the old system pattern)
            feature.points = MultiPoint(point, srid=srid)
            print(f"MultiPoint created: {feature.points}")
            
            print("Step 6: Saving feature...")
            # Save the feature
            feature.save()
            print("Feature saved successfully")

            print("Step 7: Associating with publication...")
            # Associate with the publication
            feature.publications.add(publication)
            print("Feature associated with publication")

            # Set flag to trigger session cache clearing
            self.request.session['invalidate_feature_cache'] = True              

            print("Step 8: Adding success messages...")
            messages.success(
                self.request, 
                f'Feature "{feature.name}" has been successfully created and associated with '
                f'publication {publication.number}.'
            )
            
            # Check if coordinates seem reasonable and add informational message
            if hasattr(form, 'coordinate_warnings') and form.coordinate_warnings:
                messages.warning(
                    self.request,
                    'Please verify the feature location is correct. Some coordinate values '
                    'generated warnings during validation.'
                )
            else:
                messages.info(
                    self.request,
                    'Please verify that the geographical location of the feature is correct.'
                )
            
            print("Step 9: Redirecting...")
            return redirect('publications:report', pk=publication.pk)
            
        except Exception as e:
            print(f"ERROR in form_valid: {type(e).__name__}: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            messages.error(
                self.request,
                f'Error creating feature geometry: {str(e)}. Please check your coordinates and SRID.'
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form with debugging"""
        print(f"AddFeatureCoordinatesView.form_invalid called")
        print(f"Form errors: {form.errors}")
        print(f"Form non_field_errors: {form.non_field_errors}")
        return super().form_invalid(form)
    
    def get_success_url(self):
        """Redirect to the publication detail page"""
        return reverse('publications:report', kwargs={'pk': self.kwargs['report_pk']})


class AddFeatureByMapView(LoginRequiredMixin, FormView):
    """View for adding a feature by clicking on a map"""
    template_name = 'publications/add_feature_by_map.html'
    form_class = AddFeatureByMap
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to get the publication"""
        self.publication = self.get_publication()
        return super().dispatch(request, *args, **kwargs)
    
    def get_publication(self):
        """Get the publication object"""
        report_pk = self.kwargs.get('report_pk')
        return get_object_or_404(models.Publication, pk=report_pk)
    
    def get_context_data(self, **kwargs):
        """Add publication to context"""
        context = super().get_context_data(**kwargs)
        context['publication'] = self.publication
        # Add any MapBox or other API keys if needed
        if hasattr(settings, 'MAPBOX_ACCESS_TOKEN'):
            context['mapbox_access_token'] = settings.MAPBOX_ACCESS_TOKEN
        return context
    
    def post(self, request, *args, **kwargs):
        """Process the form submission"""
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Create and save the feature with geometry from the map"""
        try:
            # Create feature object but don't save yet
            feature = form.save(commit=False)
            feature.created_by = self.request.user

            # Process geometry from the correct hidden field
            geojson_data = self.request.POST.get('geojson_data', '')
            if geojson_data:
                try:
                    # Parse the GeoJSON data
                    geojson = json.loads(geojson_data)

                    # Create a MultiPoint geometry from the coordinates
                    coordinates = []
                    if geojson.get('type') == 'FeatureCollection':
                        for f in geojson.get('features', []):
                            if f.get('geometry', {}).get('type') == 'Point':
                                coords = f['geometry']['coordinates']
                                coordinates.append(coords)

                    if coordinates:
                        print(f"DEBUG: Raw coordinates list: {coordinates}")
                        points = []
                        for idx, pair in enumerate(coordinates):
                            print(f"DEBUG: Coordinate pair {idx}: {pair} (type: {type(pair)})")
                            try:
                                lon, lat = pair
                                pt = Point(lon, lat)
                                print(f"DEBUG: Created Point: {pt} (type: {type(pt)})")
                                points.append(pt)
                            except Exception as e:
                                print(f"DEBUG: Error creating Point from {pair}: {e}")
                        print(f"DEBUG: Points list for MultiPoint: {points}")
                        print(f"DEBUG: Types in points list: {[type(p) for p in points]}")
                        geom = MultiPoint(points, srid=4326)
                        feature.points = geom
                        print(f"Created MultiPoint with {len(points)} points")
                    else:
                        raise ValueError("No valid coordinates found in map data")
                except Exception as e:
                    print(f"Error parsing GeoJSON: {str(e)}")
                    raise

            # Save the feature
            feature.save()
            print(f"Feature saved with ID: {feature.pk}")
            publication = self.get_publication()
            feature.publications.add(publication) 
            print(f"Feature added to publication {publication.pk}")
            

            messages.success(
                self.request,
                'Feature added successfully!'
            )

            return redirect('publications:report', pk=publication.pk)

        except Exception as e:
            print(f"ERROR: Exception while creating feature: {e}")
            print(traceback.format_exc())
            messages.error(
                self.request, 
                f'An error occurred while creating the feature: {str(e)}. '
                'Please try again or contact support.'
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form data"""
        print(f"AddFeatureByMapView.form_invalid called. Errors: {form.errors}")
        messages.error(
            self.request, 
            'There was a problem with your feature data. '
            'Please correct the errors below and try again.'
        )
        return super().form_invalid(form)



class DeleteFeatureView(LoginRequiredMixin, UserPassesTestMixin, DeleteView, BaseView):
    model = models.Feature
    template_name = 'publications/feature_confirm_delete.html'
    context_object_name = 'feature'

    def test_func(self):
        # User must have permission to delete the feature (customize as needed)
        feature = self.get_object()
        # Example: allow if user has global or own-feature delete permission
        return self.request.user.has_perm('publications.delete_feature') or \
               self.request.user.has_perm('publications.delete_own_feature')

    def get_success_url(self):
        # Redirect to the report page after deletion
        # Assumes feature is associated with at least one publication
        
        # Set flag to invalidate feature cache
        self.request.session['invalidate_feature_cache'] = True

        pubs = self.object.publications.all()
        if pubs.exists():
            return reverse_lazy('publications:report', kwargs={'pk': pubs.first().pk})
        return reverse_lazy('publications:reports')

    def get_context_data(self, **kwargs):
        # Ensure self.object is set before using it
        if not hasattr(self, 'object') or self.object is None:
            self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        # Ensure base_template is always present
        context['base_template'] = getattr(self, 'base_template', 'publications/base.html')
        pubs = self.object.publications.all()
        if pubs.exists():
            context['cancel_url'] = reverse_lazy('publications:report', kwargs={'pk': pubs.first().pk})
        else:
            context['cancel_url'] = reverse_lazy('publications:reports')
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Delete associated files from DB and disk
        for fileobj in self.object.files.all():
            if fileobj.file:
                fileobj.file.delete(save=False)  # Delete from disk
            fileobj.delete()  # Delete FileObject from DB
        # Optionally, handle images or other related objects here

        return super().delete(request, *args, **kwargs)


# def map_data(request):
#     features = Feature.objects.all()
#     # q: in debug mode, how to loop through features and print out the attributes?
#     # for feature in features:
#     #     print(feature)
#     serialized_features = serializers.serialize('json', features)
#     return JsonResponse(serialized_features, safe=False)