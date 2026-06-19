from odoo import models, fields, api


class ValueConfiguration(models.Model):
    _name = 'value.configuration'
    _description = 'Value Configuration for Competitive Advantage'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    # Configuration Type - Three generic value creation technologies
    configuration_type = fields.Selection([
        ('chain', 'Value Chain (Long-linked)'),
        ('shop', 'Value Shop (Intensive)'),
        ('network', 'Value Network (Mediating)'),
    ], required=True, tracking=True, help="""
        - Value Chain: Transforms inputs into products sequentially
        - Value Shop: Resolves unique customer problems cyclically
        - Value Network: Links customers through parallel activities
    """)

    # Value Creation Logic
    value_creation_logic = fields.Selection([
        ('transformation', 'Transformation of inputs into products'),
        ('problem_solving', '(Re)solving customer problems'),
        ('linking', 'Linking customers'),
    ], compute='_compute_value_creation_logic', help='Primary technology basis')

    # Activity Interactivity Pattern
    activity_interactivity = fields.Selection([
        ('sequential', 'Sequential'),
        ('cyclical', 'Cyclical, spiralling'),
        ('simultaneous', 'Simultaneous, parallel'),
    ], compute='_compute_activity_interactivity')

    # Primary Activity Interdependence
    primary_interdependence = fields.Text(compute='_compute_primary_interdependence')

    # Key Cost Drivers
    cost_drivers = fields.Text(compute='_compute_cost_drivers')

    # Key Value Drivers
    value_drivers = fields.Text(compute='_compute_value_drivers')

    # Business Value System Structure
    business_value_system = fields.Selection([
        ('interlinked_chains', 'Interlinked chains'),
        ('referred_shops', 'Referred shops'),
        ('layered_networks', 'Layered and interconnected networks'),
    ], compute='_compute_business_value_system')

    # Relationships
    activity_ids = fields.One2many('value.activity', 'configuration_id', string='Activities')
    cost_driver_ids = fields.One2many('value.driver', 'configuration_id',
                                     domain=[('driver_type', '=', 'cost')],
                                     string='Cost Drivers')
    value_driver_ids = fields.One2many('value.driver', 'configuration_id',
                                      domain=[('driver_type', '=', 'value')],
                                      string='Value Drivers')

    description = fields.Text(tracking=True)
    notes = fields.Html(tracking=True)

    @api.depends('configuration_type')
    def _compute_value_creation_logic(self):
        mapping = {
            'chain': 'transformation',
            'shop': 'problem_solving',
            'network': 'linking',
        }
        for record in self:
            record.value_creation_logic = mapping.get(record.configuration_type, False)

    @api.depends('configuration_type')
    def _compute_activity_interactivity(self):
        mapping = {
            'chain': 'sequential',
            'shop': 'cyclical',
            'network': 'simultaneous',
        }
        for record in self:
            record.activity_interactivity = mapping.get(record.configuration_type, False)

    @api.depends('configuration_type')
    def _compute_primary_interdependence(self):
        mapping = {
            'chain': 'Pooled, Sequential',
            'shop': 'Pooled, Sequential, Reciprocal',
            'network': 'Pooled, Reciprocal',
        }
        for record in self:
            record.primary_interdependence = mapping.get(record.configuration_type, '')

    @api.depends('configuration_type')
    def _compute_cost_drivers(self):
        mapping = {
            'chain': 'Scale, Capacity utilization',
            'shop': 'Scale, Capacity utilization',
            'network': 'Scale, Capacity utilization',
        }
        for record in self:
            record.cost_drivers = mapping.get(record.configuration_type, '')

    @api.depends('configuration_type')
    def _compute_value_drivers(self):
        mapping = {
            'chain': '',
            'shop': 'Reputation',
            'network': 'Scale, Capacity utilization',
        }
        for record in self:
            record.value_drivers = mapping.get(record.configuration_type, '')

    @api.depends('configuration_type')
    def _compute_business_value_system(self):
        mapping = {
            'chain': 'interlinked_chains',
            'shop': 'referred_shops',
            'network': 'layered_networks',
        }
        for record in self:
            record.business_value_system = mapping.get(record.configuration_type, False)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record._create_default_activities()
        record._create_default_drivers()
        return record

    def _create_default_activities(self):
        ActivityModel = self.env['value.activity']

        activities_map = {
            'chain': [
                ('Inbound Logistics', 'Activities associated with receiving, storing, and disseminating inputs'),
                ('Operations', 'Activities associated with transforming inputs into final product'),
                ('Outbound Logistics', 'Activities associated with collecting, storing, and distributing products'),
                ('Marketing & Sales', 'Activities associated with providing means for buyers to purchase'),
                ('Service', 'Activities associated with providing service to enhance product value'),
            ],
            'shop': [
                ('Problem-finding & Acquisition', 'Recording, reviewing, and formulating problems'),
                ('Problem-solving', 'Generating and evaluating alternative solutions'),
                ('Choice', 'Choosing among alternative solutions'),
                ('Execution', 'Communicating, organizing, and implementing chosen solution'),
                ('Control & Evaluation', 'Measuring and evaluating solution effectiveness'),
            ],
            'network': [
                ('Network Promotion & Contract Management', 'Inviting customers and managing contracts'),
                ('Service Provisioning', 'Establishing and maintaining customer links and billing'),
                ('Infrastructure Operation', 'Maintaining physical and information infrastructure'),
            ],
        }

        for activity_name, activity_desc in activities_map.get(self.configuration_type, []):
            ActivityModel.create({
                'configuration_id': self.id,
                'name': activity_name,
                'description': activity_desc,
            })

    def _create_default_drivers(self):
        DriverModel = self.env['value.driver']

        cost_drivers = [
            ('Scale', 'Economies of scale and efficiency'),
            ('Capacity Utilization', 'Optimization of resource utilization'),
        ]

        value_drivers_map = {
            'chain': [],
            'shop': [('Reputation', 'Professional reputation and success')],
            'network': [
                ('Scale', 'Network size and externalities'),
                ('Capacity Utilization', 'Service availability and reliability'),
            ],
        }

        for driver_name, driver_desc in cost_drivers:
            DriverModel.create({
                'configuration_id': self.id,
                'name': driver_name,
                'driver_type': 'cost',
                'description': driver_desc,
            })

        for driver_name, driver_desc in value_drivers_map.get(self.configuration_type, []):
            DriverModel.create({
                'configuration_id': self.id,
                'name': driver_name,
                'driver_type': 'value',
                'description': driver_desc,
            })

    def action_view_activities(self):
        return {
            'name': 'Activities',
            'type': 'ir.actions.act_window',
            'res_model': 'value.activity',
            'view_mode': 'tree,form',
            'domain': [('configuration_id', '=', self.id)],
            'context': {'default_configuration_id': self.id},
        }

    def action_view_cost_drivers(self):
        return {
            'name': 'Cost Drivers',
            'type': 'ir.actions.act_window',
            'res_model': 'value.driver',
            'view_mode': 'tree,form',
            'domain': [('configuration_id', '=', self.id), ('driver_type', '=', 'cost')],
            'context': {'default_configuration_id': self.id, 'default_driver_type': 'cost'},
        }

    def action_view_value_drivers(self):
        return {
            'name': 'Value Drivers',
            'type': 'ir.actions.act_window',
            'res_model': 'value.driver',
            'view_mode': 'tree,form',
            'domain': [('configuration_id', '=', self.id), ('driver_type', '=', 'value')],
            'context': {'default_configuration_id': self.id, 'default_driver_type': 'value'},
        }
