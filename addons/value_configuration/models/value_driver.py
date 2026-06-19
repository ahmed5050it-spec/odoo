from odoo import models, fields, api


class ValueDriver(models.Model):
    _name = 'value.driver'
    _description = 'Value Driver (Cost or Value)'
    _order = 'driver_type, sequence, id'

    name = fields.Char(required=True, tracking=True)
    configuration_id = fields.Many2one('value.configuration', required=True, ondelete='cascade')

    # Driver Classification
    driver_type = fields.Selection([
        ('cost', 'Cost Driver'),
        ('value', 'Value Driver'),
    ], required=True, help="""
        - Cost Driver: Affects the cost structure and economics
        - Value Driver: Affects customer value creation
    """)

    sequence = fields.Integer(default=10)
    description = fields.Text()

    # Driver Characteristics
    impact_level = fields.Selection([
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact'),
        ('critical', 'Critical'),
    ], help='Strategic importance of this driver')

    # Performance Tracking
    current_performance = fields.Float(help='Current performance metric value')
    target_performance = fields.Float(help='Target performance level')
    unit = fields.Char(help='Unit of measurement (e.g., %, per unit, hours)')

    # Optimization Strategy
    optimization_strategy = fields.Text(help='How to leverage or optimize this driver')
    related_activity_ids = fields.Many2many('value.activity', 'driver_activity_rel', 'driver_id',
                                           'activity_id', string='Related Activities',
                                           help='Activities most affected by this driver')

    # Strategic Notes
    strengths = fields.Text(help='Current advantages related to this driver')
    weaknesses = fields.Text(help='Current weaknesses or limitations')
    competitive_advantage = fields.Text(help='How this driver creates competitive advantage')

    notes = fields.Html()

    @api.onchange('configuration_id')
    def _onchange_configuration_id(self):
        if self.configuration_id:
            self.impact_level = 'medium'

    def name_get(self):
        result = []
        for record in self:
            type_label = dict(record._fields['driver_type'].selection).get(record.driver_type, '')
            name = f'{record.name} ({type_label})'
            result.append((record.id, name))
        return result
