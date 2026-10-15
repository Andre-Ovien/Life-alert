import json
from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator
from rest_framework.renderers import JSONRenderer
from jsonschema import Draft7Validator
from referencing import Registry,Resource
from referencing.jsonschema import DRAFT7
from incidents import tests as fixtures

class ContractTests(TestCase):
    setUp=fixtures.FoundationTests.setUp
    as_user=fixtures.FoundationTests.as_user
    accept=fixtures.FoundationTests.accept
    def test_role_scoped_responses_match_published_contract(self):
        schema=SchemaGenerator().get_schema(request=None,public=True)
        def convert(value):
            if isinstance(value,list):return [convert(item) for item in value]
            if not isinstance(value,dict):return value
            result={k:convert(v) for k,v in value.items() if k!='nullable'}
            if value.get('nullable'):return {'anyOf':[result,{'type':'null'}]}
            return result
        schema=convert(schema)
        registry=Registry().with_resource('urn:lifealert:api',Resource.from_contents(schema,default_specification=DRAFT7))
        def validate(path,method,response):
            contract=schema['paths'][path][method]['responses'][str(response.status_code)]
            body=contract.get('content',{}).get('application/json',{}).get('schema')
            self.assertIsNotNone(body,(path,response.status_code))
            wrapped={'$ref':'urn:lifealert:api'+f'#/paths/{path.replace("~","~0").replace("/","~1")}/{method}/responses/{response.status_code}/content/application~1json/schema'}
            data=json.loads(JSONRenderer().render(response.data))
            Draft7Validator(wrapped,registry=registry).validate(data)
        self.as_user(self.guardian)
        for path in ['/api/v1/children/','/api/v1/children/{id}/','/api/v1/children/{id}/readiness/',
                     '/api/v1/children/{id}/versions/','/api/v1/households/{id}/entitlement/']:
            identifier=self.household.id if 'households' in path else self.child.id
            validate(path,'get',self.client.get(path.replace('{id}',str(identifier))))
        obj=self.accept()
        for actor in [self.guardian,self.coord]:
            self.as_user(actor)
            for path in ['/api/v1/incidents/','/api/v1/incidents/{id}/','/api/v1/incidents/{id}/care/']:
                validate(path,'get',self.client.get(path.replace('{id}',str(obj.id))))
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.client.force_authenticate(user=None)
        for path in ['/api/v1/incidents/','/api/v1/incidents/{id}/']:
            validate(path,'get',self.client.get(path.replace('{id}',str(obj.id))))
        validate('/health/','get',self.client.get('/health/'))
        validate('/health/ready/','get',self.client.get('/health/ready/'))
        self.assertIn('adultBearer',schema['components']['securitySchemes'])
        self.assertIn('childDevice',schema['components']['securitySchemes'])
        help_schema=schema['paths']['/api/v1/incidents/help/']['post']
        self.assertIn('requestBody',help_schema)
        self.assertEqual(schema['paths']['/api/v1/incidents/{id}/location-updates/']['post']['requestBody']['content']['application/json']['schema']['$ref'], '#/components/schemas/IncidentViewLocationUpdatesInputRequest')
