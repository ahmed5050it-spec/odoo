from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PCFImportWizard(models.TransientModel):
    _name = 'pcf.import.wizard'
    _description = 'Import PCF Framework from Excel'

    # PCF Framework Data
    pcf_data = [
        # (PCF_ID, Hierarchy_ID, Name, Category_Code, Parent_Hierarchy_ID, Metrics)
        # 1.0 - Develop Vision and Strategy
        (10002, '1.0', 'Develop Vision and Strategy', '1.0', None, True),
        (17040, '1.1', 'Define the business concept and long-term vision', '1.0', '1.0', False),
        (10017, '1.1.1', 'Assess the external environment', '1.0', '1.1', True),
        (19945, '1.1.1.1', 'Identify competitors', '1.0', '1.1.1', False),
        (10021, '1.1.1.2', 'Analyze and Evaluate competition', '1.0', '1.1.1', False),
        (10022, '1.1.1.3', 'Identify economic trends', '1.0', '1.1.1', False),
        (10023, '1.1.1.4', 'Identify political and regulatory issues', '1.0', '1.1.1', False),
        (10024, '1.1.1.5', 'Assess new technology innovations', '1.0', '1.1.1', False),
        (10025, '1.1.1.6', 'Analyze demographics', '1.0', '1.1.1', False),
        (10026, '1.1.1.7', 'Identify social and cultural changes', '1.0', '1.1.1', False),
        (10027, '1.1.1.8', 'Identify ecological concerns', '1.0', '1.1.1', False),

        # 2.0 - Develop and Manage Products and Services
        (10003, '2.0', 'Develop and Manage Products and Services', '2.0', None, True),
        (19696, '2.1', 'Govern and manage product/service development program', '2.0', '2.0', True),
        (10061, '2.1.1', 'Manage product and service portfolio', '2.0', '2.1', True),

        # 3.0 - Market and Sell Products and Services
        (10004, '3.0', 'Market and Sell Products and Services', '3.0', None, True),
        (10101, '3.1', 'Understand markets, customers, and capabilities', '3.0', '3.0', True),
        (10106, '3.1.1', 'Perform customer and market intelligence analysis', '3.0', '3.1', True),

        # 4.0 - Deliver Physical Products
        (20022, '4.0', 'Deliver Physical Products', '4.0', None, True),
        (10215, '4.1', 'Plan for and align supply chain resources', '4.0', '4.0', True),
        (10221, '4.1.1', 'Develop production and materials strategies', '4.0', '4.1', False),

        # 5.0 - Deliver Services
        (20025, '5.0', 'Deliver Services', '5.0', None, True),
        (20026, '5.1', 'Establish service delivery governance and strategies', '5.0', '5.0', True),
        (20027, '5.1.1', 'Establish service delivery governance', '5.0', '5.1', False),

        # 6.0 - Manage Customer Service
        (20085, '6.0', 'Manage Customer Service', '6.0', None, True),
        (10378, '6.1', 'Develop customer care/customer service strategy', '6.0', '6.0', True),
        (20086, '6.1.1', 'Define customer service requirements across the enterprise', '6.0', '6.1', False),

        # 7.0 - Develop and Manage Human Capital
        (10007, '7.0', 'Develop and Manage Human Capital', '7.0', None, True),
        (17043, '7.1', 'Develop and manage HR planning, policies, and strategies', '7.0', '7.0', True),
        (20958, '7.1.1', 'Develop human resources strategy', '7.0', '7.1', False),

        # 8.0 - Manage Information Technology (IT)
        (20607, '8.0', 'Manage Information Technology (IT)', '8.0', None, True),
        (20608, '8.1', 'Develop and manage IT customer relationships', '8.0', '8.0', True),
        (20609, '8.1.1', 'Understand IT customer needs', '8.0', '8.1', False),

        # 9.0 - Manage Financial Resources
        (17058, '9.0', 'Manage Financial Resources', '9.0', None, True),
        (10728, '9.1', 'Perform planning and management accounting', '9.0', '9.0', True),
        (10738, '9.1.1', 'Perform planning/budgeting/forecasting', '9.0', '9.1', True),

        # 10.0 - Acquire, Construct, and Manage Assets
        (19207, '10.0', 'Acquire, Construct, and Manage Assets', '10.0', None, False),
        (10937, '10.1', 'Plan and acquire assets', '10.0', '10.0', False),
        (10941, '10.1.1', 'Develop property strategy and long term vision', '10.0', '10.1', False),

        # 11.0 - Manage Enterprise Risk, Compliance, Remediation, and Resiliency
        (16437, '11.0', 'Manage Enterprise Risk, Compliance, Remediation, and Resiliency', '11.0', None, False),
        (17060, '11.1', 'Manage enterprise risk', '11.0', '11.0', True),
        (16439, '11.1.1', 'Establish the enterprise risk framework and policies', '11.0', '11.1', False),

        # 12.0 - Manage External Relationships
        (10012, '12.0', 'Manage External Relationships', '12.0', None, True),
        (11010, '12.1', 'Build investor relationships', '12.0', '12.0', False),
        (11035, '12.1.1', 'Plan, build, and manage lender relations', '12.0', '12.1', False),

        # 13.0 - Develop and Manage Business Capabilities
        (10013, '13.0', 'Develop and Manage Business Capabilities', '13.0', None, True),
        (16378, '13.1', 'Manage business processes', '13.0', '13.0', False),
        (16379, '13.1.1', 'Establish and maintain process management governance', '13.0', '13.1', False),
    ]

    name = fields.Char(default='Import PCF Framework', readonly=True)
    import_status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending', readonly=True)

    imported_categories = fields.Integer(readonly=True)
    imported_processes = fields.Integer(readonly=True)
    log_message = fields.Text(readonly=True)

    def action_import_pcf(self):
        """Import PCF framework data"""
        try:
            self.import_status = 'in_progress'

            PCFCategory = self.env['pcf.category']
            PCFProcess = self.env['pcf.process']

            # Track created categories and processes
            categories = {}
            processes = {}

            # Create categories first (main categories only: 1.0, 2.0, ..., 13.0)
            main_categories = [(code, name) for (_, code, name, _, _, metrics)
                             in self.pcf_data if len(code.split('.')) == 2 and code.endswith('.0')]

            for code, name in main_categories:
                if code not in categories:
                    cat = PCFCategory.create({
                        'code': code,
                        'name': name,
                        'metrics_available': any(metrics for pcf_id, h_id, n, cat_code, parent, metrics
                                               in self.pcf_data if cat_code == code),
                    })
                    categories[code] = cat
                    _logger.info(f'Created PCF Category: {code}')

            # Create processes
            for pcf_id, hierarchy_id, name, category_code, parent_hierarchy_id, metrics in self.pcf_data:
                parent_process = None
                if parent_hierarchy_id:
                    parent_process = processes.get(parent_hierarchy_id)

                process = PCFProcess.create({
                    'pcf_id': pcf_id,
                    'hierarchy_id': hierarchy_id,
                    'name': name,
                    'category_id': categories[category_code].id,
                    'parent_id': parent_process.id if parent_process else None,
                    'metrics_available': metrics,
                })
                processes[hierarchy_id] = process
                _logger.info(f'Created PCF Process: {hierarchy_id}')

            self.imported_categories = len(categories)
            self.imported_processes = len(processes)
            self.import_status = 'completed'
            self.log_message = f"""
            PCF Framework Import Completed Successfully!

            Imported:
            - {len(categories)} Main Categories
            - {len(processes)} Processes/Sub-processes

            The PCF framework is now available for mapping to your value configurations.

            Next Steps:
            1. Go to Value Configurations
            2. Create or edit a configuration
            3. In the "PCF Framework Mappings" tab, add mappings between PCF processes and value activities
            """

        except Exception as e:
            _logger.error(f'PCF Import Failed: {str(e)}')
            self.import_status = 'failed'
            self.log_message = f'Import Failed: {str(e)}\n\nPlease check the logs for more details.'
            raise UserError(f'PCF Import Error: {str(e)}')
