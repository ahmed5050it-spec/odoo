{
    'name': 'Value Configuration Framework',
    'version': '1.0.0',
    'category': 'Tools',
    'summary': 'Implement value configuration methodology based on Stabell & Fjeldstad framework',
    'description': '''
        This module implements the value configuration framework for competitive advantage.
        It supports three value creation logics:

        1. Value Chain (Long-linked technology)
           - Sequential activities focused on cost
           - Transforms inputs into products

        2. Value Shop (Intensive technology)
           - Cyclical activities focused on value
           - Resolves unique customer problems

        3. Value Network (Mediating technology)
           - Parallel activities balancing cost and value
           - Links customers and enables exchanges
    ''',
    'author': 'Value Configuration Module',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/value_configuration_views.xml',
        'views/value_activity_views.xml',
        'views/value_driver_views.xml',
        'views/pcf_views.xml',
        'views/pcf_import_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
}
