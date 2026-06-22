from odoo import models, fields, api


class PCFActivityMapping(models.Model):
    _name = 'pcf.activity.mapping'
    _description = 'Mapping between PCF Processes and Value Configuration Activities'
    _order = 'pcf_process_id, value_activity_id'

    # PCF side
    pcf_category_id = fields.Many2one('pcf.category', string='PCF Category',
                                     help='Broader category for reference')
    pcf_process_id = fields.Many2one('pcf.process', required=True, ondelete='cascade',
                                    string='PCF Process')

    # Value Configuration side
    value_configuration_id = fields.Many2one('value.configuration', required=True,
                                            ondelete='cascade', string='Value Configuration')
    value_activity_id = fields.Many2one('value.activity', required=True, ondelete='cascade',
                                       string='Value Activity')

    # Mapping Details
    relevance_level = fields.Selection([
        ('primary', 'Primary - Core to this activity'),
        ('secondary', 'Secondary - Supports the activity'),
        ('tertiary', 'Tertiary - Occasional reference'),
    ], default='primary', help='How relevant is this PCF process to the value activity')

    description = fields.Text(help='Description of how this process maps to the activity')
    process_percentage = fields.Float(help='% of activity effort spent on this process')

    # Cross-Industry Mapping
    applicable_industries = fields.Char(help='Industries where this mapping is relevant')
    configuration_type = fields.Selection([
        ('chain', 'Value Chain'),
        ('shop', 'Value Shop'),
        ('network', 'Value Network'),
    ], compute='_compute_configuration_type', store=True, help='Which value configuration type')

    # Metrics Tracking
    pcf_has_metrics = fields.Boolean(related='pcf_process_id.metrics_available', readonly=True,
                                    string='PCF Metrics Available?')
    kpi_ids = fields.One2many('pcf.activity.kpi', 'mapping_id', string='Key Performance Indicators')

    notes = fields.Html()

    @api.depends('value_configuration_id')
    def _compute_configuration_type(self):
        for record in self:
            if record.value_configuration_id:
                record.configuration_type = record.value_configuration_id.configuration_type

    @api.constraints('pcf_process_id', 'value_activity_id')
    def _check_unique_mapping(self):
        for record in self:
            # Allow multiple mappings, but this helps identify them
            pass

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.pcf_process_id.hierarchy_id} → {record.value_activity_id.name}'
            result.append((record.id, name))
        return result


class PCFActivityKPI(models.Model):
    _name = 'pcf.activity.kpi'
    _description = 'KPI for PCF-Activity Mapping'
    _order = 'sequence'

    mapping_id = fields.Many2one('pcf.activity.mapping', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    # KPI Definition
    name = fields.Char(required=True, help='KPI name or code')
    description = fields.Text(help='What this KPI measures')
    unit = fields.Char(help='Unit of measurement (%, count, hours, etc.)')
    category = fields.Selection([
        ('cost', 'Cost KPI'),
        ('quality', 'Quality KPI'),
        ('time', 'Time/Speed KPI'),
        ('effectiveness', 'Effectiveness KPI'),
        ('efficiency', 'Efficiency KPI'),
    ], help='Type of KPI')

    # Performance Tracking
    current_value = fields.Float(help='Current performance')
    target_value = fields.Float(help='Target/desired performance')
    benchmark_value = fields.Float(help='Industry benchmark if available')

    # Source
    source = fields.Selection([
        ('pcf', 'From PCF Framework'),
        ('organization', 'Organization-defined'),
        ('industry', 'Industry Standard'),
        ('custom', 'Custom'),
    ], default='pcf', help='Where this KPI comes from')

    notes = fields.Html()


class ValueConfigurationPCFMapping(models.Model):
    _name = 'value.configuration.pcf'
    _description = 'PCF Mapping for Value Configuration'
    _inherit = 'value.configuration'

    # Summary of mapped PCF processes
    pcf_mapping_count = fields.Integer(compute='_compute_pcf_mapping_count', string='PCF Mappings')
    pcf_category_ids = fields.Many2many('pcf.category', compute='_compute_pcf_categories',
                                       string='Related PCF Categories')
    pcf_mapping_ids = fields.One2many('pcf.activity.mapping', 'value_configuration_id',
                                     string='PCF Activity Mappings')

    # PCF Process Governance
    pcf_version = fields.Char(help='PCF version used (e.g., 7.2.1)')
    pcf_adoption_level = fields.Selection([
        ('none', 'Not Using PCF'),
        ('partial', 'Using Selected Processes'),
        ('full', 'Full PCF Adoption'),
    ], default='none', help='How much PCF is being used')

    @api.depends('pcf_mapping_ids')
    def _compute_pcf_mapping_count(self):
        for record in self:
            record.pcf_mapping_count = len(record.pcf_mapping_ids)

    @api.depends('pcf_mapping_ids')
    def _compute_pcf_categories(self):
        for record in self:
            categories = record.pcf_mapping_ids.mapped('pcf_category_id')
            record.pcf_category_ids = categories

    def action_view_pcf_mappings(self):
        return {
            'name': 'PCF Mappings',
            'type': 'ir.actions.act_window',
            'res_model': 'pcf.activity.mapping',
            'view_mode': 'tree,form',
            'domain': [('value_configuration_id', '=', self.id)],
            'context': {'default_value_configuration_id': self.id},
        }
