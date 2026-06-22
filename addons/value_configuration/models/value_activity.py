from odoo import models, fields, api


class ValueActivity(models.Model):
    _name = 'value.activity'
    _description = 'Value Activity'
    _order = 'sequence, id'

    name = fields.Char(required=True, tracking=True)
    configuration_id = fields.Many2one('value.configuration', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    description = fields.Text()

    # Activity Classification
    activity_type = fields.Selection([
        ('primary', 'Primary Activity'),
        ('support', 'Support Activity'),
    ], default='primary', help='Primary activities directly create value; support activities enable them')

    # Activity Characteristics
    is_core_competency = fields.Boolean(help='Mark if this is a critical competency')
    cost_percentage = fields.Float(help='Estimated percentage of total cost')
    value_impact = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], help='Impact on customer value')

    # Interdependencies
    depends_on_ids = fields.Many2many('value.activity', 'activity_dependency_rel', 'activity_id',
                                      'depends_on_id', string='Depends On')
    related_activity_ids = fields.Many2many('value.activity', 'activity_relation_rel', 'activity_id',
                                           'related_activity_id', string='Related Activities')

    # Performance Metrics
    performance_metric = fields.Char(help='Key metric to measure this activity')
    benchmark_value = fields.Float(help='Benchmark or target value')

    # Strategic Notes
    strengths = fields.Text(help='Current strengths in this activity')
    weaknesses = fields.Text(help='Current weaknesses or improvement areas')
    improvement_opportunities = fields.Text(help='Strategic improvement opportunities')

    notes = fields.Html()

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.sequence}. {record.name}'
            result.append((record.id, name))
        return result

    @api.onchange('configuration_id')
    def _onchange_configuration_id(self):
        if self.configuration_id:
            self.value_impact = 'medium'
