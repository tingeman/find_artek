from django.core.management.base import BaseCommand
from publications.models import Feature


class Command(BaseCommand):
    help = 'Analyze SRID usage in the Feature model geometry fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample-size',
            type=int,
            default=10,
            help='Number of sample features to display (default: 10)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed geometry information'
        )

    def handle(self, *args, **options):
        sample_size = options['sample_size']
        verbose = options['verbose']

        self.stdout.write(self.style.SUCCESS('=== FEATURE SRID ANALYSIS ===\n'))

        try:
            # Count total features
            total = Feature.objects.count()
            self.stdout.write(f"Total features in database: {total}")

            # Count features with geometry data
            with_points = Feature.objects.filter(points__isnull=False).count()
            with_lines = Feature.objects.filter(lines__isnull=False).count()
            with_polys = Feature.objects.filter(polys__isnull=False).count()

            self.stdout.write(f"Features with points: {with_points}")
            self.stdout.write(f"Features with lines: {with_lines}")
            self.stdout.write(f"Features with polygons: {with_polys}")

            # Check sample features with points
            if with_points > 0:
                self.stdout.write(self.style.SUCCESS(f'\n=== SAMPLE FEATURES WITH POINTS (showing {sample_size}) ==='))
                sample_features = Feature.objects.filter(points__isnull=False)[:sample_size]
                
                for feature in sample_features:
                    if feature.points:
                        self.stdout.write(f"Feature ID {feature.id}: {feature.name}")
                        self.stdout.write(f"  SRID: {feature.points.srid}")
                        if verbose:
                            self.stdout.write(f"  Geometry type: {feature.points.geom_type}")
                            self.stdout.write(f"  Coordinates: {feature.points}")
                        self.stdout.write('')

            # Check sample features with lines
            if with_lines > 0:
                self.stdout.write(self.style.SUCCESS(f'\n=== SAMPLE FEATURES WITH LINES (showing {min(sample_size, 5)}) ==='))
                sample_features = Feature.objects.filter(lines__isnull=False)[:min(sample_size, 5)]
                
                for feature in sample_features:
                    if feature.lines:
                        self.stdout.write(f"Feature ID {feature.id}: {feature.name}")
                        self.stdout.write(f"  SRID: {feature.lines.srid}")
                        if verbose:
                            self.stdout.write(f"  Geometry type: {feature.lines.geom_type}")
                        self.stdout.write('')

            # Check sample features with polygons
            if with_polys > 0:
                self.stdout.write(self.style.SUCCESS(f'\n=== SAMPLE FEATURES WITH POLYGONS (showing {min(sample_size, 5)}) ==='))
                sample_features = Feature.objects.filter(polys__isnull=False)[:min(sample_size, 5)]
                
                for feature in sample_features:
                    if feature.polys:
                        self.stdout.write(f"Feature ID {feature.id}: {feature.name}")
                        self.stdout.write(f"  SRID: {feature.polys.srid}")
                        if verbose:
                            self.stdout.write(f"  Geometry type: {feature.polys.geom_type}")
                        self.stdout.write('')

            # Get unique SRIDs used in the database
            self.stdout.write(self.style.SUCCESS('\n=== UNIQUE SRIDs IN USE ==='))
            
            # For points
            point_features = Feature.objects.filter(points__isnull=False)
            point_srids = set()
            for f in point_features:
                if f.points:
                    point_srids.add(f.points.srid)
            self.stdout.write(f"Point SRIDs used: {sorted(point_srids)}")
            
            # For lines
            line_features = Feature.objects.filter(lines__isnull=False)
            line_srids = set()
            for f in line_features:
                if f.lines:
                    line_srids.add(f.lines.srid)
            self.stdout.write(f"Line SRIDs used: {sorted(line_srids)}")
            
            # For polygons
            poly_features = Feature.objects.filter(polys__isnull=False)
            poly_srids = set()
            for f in poly_features:
                if f.polys:
                    poly_srids.add(f.polys.srid)
            self.stdout.write(f"Polygon SRIDs used: {sorted(poly_srids)}")

            # Summary
            all_srids = point_srids.union(line_srids).union(poly_srids)
            self.stdout.write(self.style.SUCCESS(f'\n=== SUMMARY ==='))
            self.stdout.write(f"Total unique SRIDs in database: {sorted(all_srids)}")
            
            if len(all_srids) == 1 and 4326 in all_srids:
                self.stdout.write(self.style.SUCCESS("✓ All geometry data uses SRID 4326 (WGS84)"))
            elif len(all_srids) > 1:
                self.stdout.write(self.style.WARNING(f"⚠ Multiple SRIDs detected: {sorted(all_srids)}"))
            else:
                self.stdout.write(self.style.ERROR("✗ No SRID data found or unexpected SRID"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
