import logging

from datetime import datetime
from flask_restful import reqparse

from servicex_app.decorators import auth_required
from servicex_app.models import DatasetFile
from servicex_app.resources.servicex_resource import ServiceXResource

parser = reqparse.RequestParser()
parser.add_argument('cutoff', type=str, location='args', required=False)

logger = logging.getLogger(__name__)


class GetDatasetFilesSince(ServiceXResource):
    @auth_required
    def get(self):
        args = parser.parse_args()
        files_query = DatasetFile.query

        if args.get('cutoff'):
            cutoff_str = args['cutoff']

            try:
                if cutoff_str.endswith('Z'):
                    cutoff_str = cutoff_str[:-1] + '+00:00'

                cutoff_datetime = datetime.fromisoformat(cutoff_str)

                files_query = files_query.filter(DatasetFile.created_at >= cutoff_datetime)

                logger.debug(f"Filtering files created after {cutoff_datetime}")
            except ValueError as e:
                logger.error(f"Error parsing cutoff datetime: {e}")
                return {
                    'message': f"Invalid cutoff parameter: {cutoff_str}. Must be a valid ISO 8601 datetime (YYYY-MM-DDTHH:MM:SS+00:00)"
                }, 400

        files = [file.to_json() for file in files_query]
        return {
            "files": files
        }
